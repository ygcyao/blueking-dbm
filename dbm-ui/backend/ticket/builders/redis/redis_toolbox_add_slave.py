# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making 蓝鲸智云-DB管理系统(BlueKing-BK-DBM) available.
Copyright (C) 2017-2023 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import itertools

from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from backend.configuration.constants import AffinityEnum
from backend.db_meta.enums import InstanceRole, InstanceStatus
from backend.db_meta.models import Cluster, Machine, StorageInstanceTuple
from backend.db_services.dbbase.constants import IpSource
from backend.flow.engine.controller.redis import RedisController
from backend.ticket import builders
from backend.ticket.builders.common.base import BaseOperateResourceParamBuilder, SkipToRepresentationMixin
from backend.ticket.builders.redis.base import BaseRedisTicketFlowBuilder, ClusterValidateMixin
from backend.ticket.constants import TicketType
from backend.utils.basic import get_target_items_from_details


class RedisAddSlaveDetailSerializer(SkipToRepresentationMixin, serializers.Serializer):
    """新建从库"""

    class InfoSerializer(ClusterValidateMixin, serializers.Serializer):
        cluster_ids = serializers.ListField(help_text=_("集群ID列表"), child=serializers.IntegerField())
        bk_cloud_id = serializers.IntegerField(help_text=_("云区域ID"))
        pairs = serializers.ListField(help_text=_("主从切换对"), child=serializers.DictField())

        def validate(self, attr):
            """业务逻辑校验"""
            cluster = Cluster.objects.get(id=attr["cluster_ids"][0])
            for pair in attr["pairs"]:
                redis_master = pair["redis_master"]["bk_host_id"]
                if not StorageInstanceTuple.objects.filter(
                    ejector__machine__bk_host_id=redis_master,
                    receiver__instance_role=InstanceRole.REDIS_SLAVE,
                    receiver__status=InstanceStatus.UNAVAILABLE,
                ).exists():
                    raise serializers.ValidationError(_("集群{}不存在异常的从库主机").format(cluster.immute_domain))
            return attr

    ip_source = serializers.ChoiceField(help_text=_("主机来源"), choices=IpSource.get_choices())
    infos = serializers.ListField(help_text=_("批量操作参数列表"), child=InfoSerializer())


class RedisAddSlaveParamBuilder(builders.FlowParamBuilder):
    controller = RedisController.redis_cluster_add_slave

    def format_ticket_data(self):
        super().format_ticket_data()


class RedisAddSlaveResourceParamBuilder(BaseOperateResourceParamBuilder):
    def post_callback(self):
        next_flow = self.ticket.next_flow()
        ticket_data = next_flow.details["ticket_data"]

        for info_index, info in enumerate(ticket_data["infos"]):
            for pair in info["pairs"]:
                pair["redis_slave"] = info.pop(pair["redis_master"]["ip"], [])

        next_flow.save(update_fields=["details"])
        super().post_callback()


@builders.BuilderFactory.register(TicketType.REDIS_CLUSTER_ADD_SLAVE, is_apply=True)
class RedisAddSlaveFlowBuilder(BaseRedisTicketFlowBuilder):
    serializer = RedisAddSlaveDetailSerializer
    inner_flow_builder = RedisAddSlaveParamBuilder
    inner_flow_name = _("Redis 新建从库")
    resource_batch_apply_builder = RedisAddSlaveResourceParamBuilder
    default_need_itsm = False

    def patch_ticket_detail(self):
        """redis_master -> backend_group"""

        super().patch_ticket_detail()
        master_hosts = get_target_items_from_details(self.ticket.details, match_keys=["bk_host_id"])
        id__machine = {
            machine.bk_host_id: machine
            for machine in Machine.objects.prefetch_related("bk_city__logical_city").filter(
                bk_host_id__in=master_hosts
            )
        }
        cluster_ids = list(itertools.chain(*[infos["cluster_ids"] for infos in self.ticket.details["infos"]]))
        id__cluster = {cluster.id: cluster for cluster in Cluster.objects.filter(id__in=cluster_ids)}

        for info in self.ticket.details["infos"]:
            info["resource_spec"] = {}
            # 取第一个cluster即可，即使是多集群，也是单机多实例的情况
            cluster = id__cluster[info["cluster_ids"][0]]
            for pair in info["pairs"]:
                # 申请的 new slave, 需要和当前集群中的 master 不同机房;
                master_machine = id__machine[pair["redis_master"]["bk_host_id"]]
                pair["redis_slave"]["location_spec"] = {
                    "city": master_machine.bk_city.logical_city.name,
                    "sub_zone_ids": [],
                }
                pair["redis_slave"].update(affinity=cluster.disaster_tolerance_level)
                if cluster.disaster_tolerance_level == AffinityEnum.CROS_SUBZONE:
                    pair["redis_slave"]["location_spec"].update(
                        sub_zone_ids=[master_machine.bk_sub_zone_id], include_or_exclue=False
                    )

                elif cluster.disaster_tolerance_level in [
                    AffinityEnum.SAME_SUBZONE,
                    AffinityEnum.SAME_SUBZONE_CROSS_SWTICH,
                ]:
                    pair["redis_slave"]["location_spec"].update(
                        sub_zone_ids=[master_machine.bk_sub_zone_id], include_or_exclue=True
                    )
                info["resource_spec"][pair["redis_master"]["ip"]] = pair["redis_slave"]

        self.ticket.save(update_fields=["details"])
