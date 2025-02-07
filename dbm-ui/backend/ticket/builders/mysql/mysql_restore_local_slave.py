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

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from backend.db_meta.enums import ClusterType, InstanceInnerRole
from backend.flow.engine.controller.mysql import MySQLController
from backend.ticket import builders
from backend.ticket.builders.common.base import InstanceInfoSerializer, fetch_cluster_ids
from backend.ticket.builders.common.constants import MySQLBackupSource
from backend.ticket.builders.mysql.base import BaseMySQLHATicketFlowBuilder, MySQLBaseOperateDetailSerializer
from backend.ticket.constants import TicketType


class MysqlRestoreLocalSlaveDetailSerializer(MySQLBaseOperateDetailSerializer):
    class SlaveInfoSerializer(serializers.Serializer):
        slave = InstanceInfoSerializer(help_text=_("从库实例信息"))
        cluster_id = serializers.IntegerField(help_text=_("集群ID"))

    infos = serializers.ListField(help_text=_("重建从库列表"), child=SlaveInfoSerializer())
    backup_source = serializers.ChoiceField(help_text=_("备份源"), choices=MySQLBackupSource.get_choices())
    force = serializers.BooleanField(help_text=_("是否强制执行"), required=False, default=False)

    def validate(self, attrs):
        cluster_ids = fetch_cluster_ids(attrs)

        # 校验集群是否可用，集群类型为高可用
        super(MysqlRestoreLocalSlaveDetailSerializer, self).validate_cluster_can_access(attrs)
        super(MysqlRestoreLocalSlaveDetailSerializer, self).validated_cluster_type(attrs, ClusterType.TenDBHA)

        # 校验实例的角色为slave
        super(MysqlRestoreLocalSlaveDetailSerializer, self).validate_instance_role(
            attrs, instance_key=["slave"], role=InstanceInnerRole.SLAVE
        )

        # 校验实例属于当前集群
        super(MysqlRestoreLocalSlaveDetailSerializer, self).validate_instance_related_clusters(
            attrs, instance_key=["slave"], cluster_key=["cluster_id"], role=InstanceInnerRole.SLAVE
        )

        # 校验集群存在最近一次全备
        super(MysqlRestoreLocalSlaveDetailSerializer, self).validated_cluster_latest_backup(
            cluster_ids, attrs["backup_source"]
        )

        return attrs


class MysqlRestoreLocalSlaveParamBuilder(builders.FlowParamBuilder):
    controller = MySQLController.mysql_restore_local_remote_scene

    def format_ticket_data(self):
        for index, info in enumerate(self.ticket_data["infos"]):
            bk_slave = info.pop("slave")
            self.ticket_data["infos"][index].update(
                slave_ip=bk_slave["ip"], slave_port=int(bk_slave["port"]), bk_slave=bk_slave
            )


@builders.BuilderFactory.register(TicketType.MYSQL_RESTORE_LOCAL_SLAVE)
class MysqlRestoreLocalSlaveFlowBuilder(BaseMySQLHATicketFlowBuilder):
    serializer = MysqlRestoreLocalSlaveDetailSerializer
    inner_flow_builder = MysqlRestoreLocalSlaveParamBuilder
    inner_flow_name = _("Slave原地重建执行")
