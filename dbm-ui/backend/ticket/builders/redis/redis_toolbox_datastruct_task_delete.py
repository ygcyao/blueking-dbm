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
import operator
from functools import reduce

from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from backend.db_meta.enums import DestroyedStatus
from backend.db_meta.models import Cluster, Machine
from backend.db_services.redis.rollback.models import TbTendisRollbackTasks
from backend.flow.engine.controller.redis import RedisController
from backend.ticket import builders
from backend.ticket.builders.common.base import DisplayInfoSerializer
from backend.ticket.builders.common.base import HostRecycleSerializer, SkipToRepresentationMixin
from backend.ticket.builders.redis.base import BaseRedisTicketFlowBuilder, RedisBasePauseParamBuilder
from backend.ticket.constants import TicketType


class RedisDataStructureTaskDeleteDetailSerializer(SkipToRepresentationMixin, serializers.Serializer):
    """数据构造与实例销毁"""

    class InfoSerializer(DisplayInfoSerializer):
        related_rollback_bill_id = serializers.CharField(help_text=_("关联单据ID"))
        cluster_id = serializers.IntegerField(help_text=_("集群ID"))
        bk_cloud_id = serializers.IntegerField(help_text=_("云区域ID"))

        def validate(self, attr):
            """业务逻辑校验"""
            # 判断集群是否存在
            try:
                prod_cluster = Cluster.objects.get(id=attr["cluster_id"])
            except Cluster.DoesNotExist:
                raise serializers.ValidationError(_("目标集群{}不存在，请确认.").format(attr["cluster_id"]))

            # 判断构造实例是否存在
            tasks = TbTendisRollbackTasks.objects.filter(
                related_rollback_bill_id=attr.get("related_rollback_bill_id"),
                prod_cluster=prod_cluster.immute_domain,
                bk_cloud_id=attr.get("bk_cloud_id"),
                destroyed_status=DestroyedStatus.NOT_DESTROYED,
            )
            if not tasks.exists():
                raise serializers.ValidationError(_("集群{}: 没有找到未销毁的实例.").format(prod_cluster.immute_domain))

            # 填写域名
            attr["prod_cluster"] = prod_cluster.immute_domain
            # 填写构造任务，patch函数用
            attr["datastruct_tasks"] = tasks
            return attr

    infos = serializers.ListField(help_text=_("批量操作参数列表"), child=InfoSerializer())
    ip_recycle = HostRecycleSerializer(help_text=_("主机回收信息"), default=HostRecycleSerializer.DEFAULT)


class RedisDataStructureTaskDeleteParamBuilder(builders.FlowParamBuilder):
    controller = RedisController.redis_data_structure_task_delete


@builders.BuilderFactory.register(TicketType.REDIS_DATA_STRUCTURE_TASK_DELETE, is_recycle=True)
class RedisDataStructureTaskDeleteFlowBuilder(BaseRedisTicketFlowBuilder):
    serializer = RedisDataStructureTaskDeleteDetailSerializer
    inner_flow_builder = RedisDataStructureTaskDeleteParamBuilder
    inner_flow_name = _("Redis 销毁构造实例")
    pause_node_builder = RedisBasePauseParamBuilder
    need_patch_recycle_host_details = True

    def patch_datastruct_delete_nodes(self):
        drop_machine_filters = []
        for info in self.ticket.details["infos"]:
            tasks = info.pop("datastruct_tasks")
            instances = itertools.chain(*[task.temp_instance_range for task in tasks])
            filters = [
                Q(bk_biz_id=tasks[0].bk_biz_id, bk_cloud_id=tasks[0].bk_cloud_id, ip=instance.split(":")[0])
                for instance in instances
            ]
            drop_machine_filters.extend(filters)

        drop_machines = Machine.objects.filter(reduce(operator.or_, drop_machine_filters))
        self.ticket.details["old_nodes"]["datastruct_hosts"] = [
            {"ip": host.ip, "bk_host_id": host.bk_host_id} for host in drop_machines
        ]

    def patch_ticket_detail(self):
        self.patch_datastruct_delete_nodes()
        super().patch_ticket_detail()
