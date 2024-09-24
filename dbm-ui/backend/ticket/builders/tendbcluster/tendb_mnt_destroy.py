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
from backend.ticket.builders.common.base import HostRecycleSerializer
from backend.ticket.builders.tendbcluster.base import BaseTendbTicketFlowBuilder, TendbBaseOperateDetailSerializer
from backend.ticket.constants import TicketType


class TendbMNTDestroyDetailSerializer(TendbBaseOperateDetailSerializer):
    class MNTDestroySerializer(serializers.Serializer):
        class OldMNTSerializer(serializers.Serializer):
            spider_ip_list = serializers.ListField(child=serializers.DictField())

        cluster_id = serializers.IntegerField(help_text=_("集群ID"))
        old_nodes = OldMNTSerializer(help_text=_("运维节点信息"))

    infos = serializers.ListField(help_text=_("下架spider运维节点信息"), child=MNTDestroySerializer())
    is_safe = serializers.BooleanField(help_text=_("是否安全模式执行"), required=False, default=True)
    ip_recycle = HostRecycleSerializer(help_text=_("主机回收信息"), default=HostRecycleSerializer.DEFAULT)

    def validate(self, attrs):
        super().validate(attrs)
        return attrs


class TendbMNTDestroyParamBuilder(builders.FlowParamBuilder):
    controller = SpiderController.reduce_spider_mnt_scene


@builders.BuilderFactory.register(TicketType.TENDBCLUSTER_SPIDER_MNT_DESTROY, is_recycle=True)
class TendbMNTDestroyFlowBuilder(BaseTendbTicketFlowBuilder):
    serializer = TendbMNTDestroyDetailSerializer
    inner_flow_builder = TendbMNTDestroyParamBuilder
    inner_flow_name = _("TendbCluster 下架运维节点")
    need_patch_recycle_host_details = True
