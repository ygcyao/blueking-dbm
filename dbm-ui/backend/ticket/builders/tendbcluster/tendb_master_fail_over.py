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

from backend.flow.engine.controller.spider import SpiderController
from backend.ticket import builders
from backend.ticket.builders.tendbcluster.base import BaseTendbTicketFlowBuilder, TendbBaseOperateDetailSerializer
from backend.ticket.builders.tendbcluster.tendb_master_slave_switch import TendbMasterSlaveSwitchDetailSerializer
from backend.ticket.constants import TicketType


class TendbMasterFailOverDetailSerializer(TendbMasterSlaveSwitchDetailSerializer):
    force = serializers.BooleanField(help_text=_("是否强制执行(互切不强制，故障切强制)"), required=False, default=True)
    serializers.BooleanField(help_text=_("是否检测数据同步延时情况"))

    def validate(self, attrs):
        # 校验集群是否可用，集群类型为tendbcluster
        super(TendbBaseOperateDetailSerializer, self).validate_cluster_can_access(attrs)
        if not attrs["force"]:
            raise serializers.ValidationError(_("主故障切换场景需要强制执行"))

        return attrs


class TendbMasterFailOverParamBuilder(builders.FlowParamBuilder):
    controller = SpiderController.tendbcluster_remote_fail_over_scene


@builders.BuilderFactory.register(TicketType.TENDBCLUSTER_MASTER_FAIL_OVER)
class TendbMasterFailOverFlowBuilder(BaseTendbTicketFlowBuilder):
    serializer = TendbMasterFailOverDetailSerializer
    inner_flow_builder = TendbMasterFailOverParamBuilder
    inner_flow_name = _("TendbCluster 主故障切换")
