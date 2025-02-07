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

from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from backend.db_meta.enums import ClusterType
from backend.flow.consts import TruncateDataTypeEnum
from backend.flow.engine.controller.mysql import MySQLController
from backend.ticket import builders
from backend.ticket.builders.mysql.base import (
    BaseMySQLHATicketFlowBuilder,
    DBTableField,
    MySQLBaseOperateDetailSerializer,
)
from backend.ticket.constants import TicketType


class MySQLHaClearDetailSerializer(MySQLBaseOperateDetailSerializer):
    class TruncateDataInfoSerializer(serializers.Serializer):
        cluster_id = serializers.IntegerField(help_text=_("集群ID"))
        db_patterns = serializers.ListField(help_text=_("匹配DB列表"), child=DBTableField(db_field=True))
        ignore_dbs = serializers.ListField(help_text=_("忽略DB列表"), child=DBTableField(db_field=True))
        table_patterns = serializers.ListField(help_text=_("匹配Table列表"), child=DBTableField())
        ignore_tables = serializers.ListField(help_text=_("忽略Table列表"), child=DBTableField())
        truncate_data_type = serializers.ChoiceField(help_text=_("清档类型"), choices=TruncateDataTypeEnum.get_choices())
        force = serializers.BooleanField(help_text=_("是否强制执行"), default=False)

    infos = serializers.ListSerializer(help_text=_("清档信息列表"), child=TruncateDataInfoSerializer())

    def validate(self, attrs):
        """校验库表选择器信息是否正确"""
        super().validate_cluster_can_access(attrs)
        # 库表选择器校验
        super().validate_database_table_selector(attrs)
        # 校验集群类型只能是高可用
        super().validated_cluster_type(attrs, cluster_type=ClusterType.TenDBHA)
        return attrs


class MySQLHaClearFlowParamBuilder(builders.FlowParamBuilder):
    """MySQL清档执行单据参数"""

    controller = MySQLController.mysql_ha_truncate_data_scene

    def format_ticket_data(self):
        pass


@builders.BuilderFactory.register(TicketType.MYSQL_HA_TRUNCATE_DATA)
class MySQLHaClearFlowBuilder(BaseMySQLHATicketFlowBuilder):
    serializer = MySQLHaClearDetailSerializer
    inner_flow_builder = MySQLHaClearFlowParamBuilder
    inner_flow_name = _("清档执行")
