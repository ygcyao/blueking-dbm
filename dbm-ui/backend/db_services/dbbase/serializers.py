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

from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from backend.components import CCApi
from backend.configuration.constants import DBType
from backend.db_dirty.models import DirtyMachine
from backend.db_meta.enums import ClusterPhase, ClusterType
from backend.db_meta.models import Cluster
from backend.db_services.dbbase.constants import ResourceType
from backend.db_services.dbbase.resources.serializers import ListClusterEntriesSLZ, ListResourceSLZ
from backend.db_services.ipchooser.query.resource import ResourceQueryHelper
from backend.db_services.redis.resources.redis_cluster.query import RedisListRetrieveResource
from backend.dbm_init.constants import CC_APP_ABBR_ATTR
from backend.ticket.constants import TicketType


class IsClusterDuplicatedSerializer(serializers.Serializer):
    cluster_type = serializers.ChoiceField(help_text=_("集群类型"), choices=ClusterType.get_choices())
    name = serializers.CharField(help_text=_("集群名"))
    bk_biz_id = serializers.IntegerField(help_text=_("业务ID"))


class IsClusterDuplicatedResponseSerializer(serializers.Serializer):
    class Meta:
        swagger_schema_fields = {"example": {"is_duplicated": True}}


class QueryAllTypeClusterSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(help_text=_("业务ID"))
    cluster_types = serializers.CharField(help_text=_("集群类型(逗号分隔)"), required=False)
    immute_domain = serializers.CharField(help_text=_("集群域名"), required=False)
    # 额外过滤参数
    phase = serializers.ChoiceField(help_text=_("集群阶段状态"), required=False, choices=ClusterPhase.get_choices())

    def get_conditions(self, attr):
        conditions = {"bk_biz_id": attr["bk_biz_id"]}
        if attr.get("cluster_types"):
            conditions["cluster_type__in"] = attr["cluster_types"].split(",")
        if attr.get("immute_domain"):
            conditions["immute_domain__icontains"] = attr["immute_domain"]
        # 额外过滤参数
        if attr.get("phase"):
            conditions["phase"] = attr["phase"]
        return conditions


class QueryAllTypeClusterResponseSerializer(serializers.Serializer):
    class Meta:
        swagger_schema_fields = {"example": [{"id": 47, "immute_domain": "mysql.dba.db.com"}]}


class CommonQueryClusterSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(help_text=_("业务ID"))
    cluster_types = serializers.CharField(help_text=_("集群类型(逗号分隔)"))
    cluster_ids = serializers.CharField(help_text=_("集群ID(逗号分割)"), required=False, default="")

    def validate(self, attrs):
        attrs["cluster_types"] = attrs["cluster_types"].split(",")
        attrs["cluster_ids"] = attrs["cluster_ids"].split(",") if attrs["cluster_ids"] else []
        return attrs


class CommonQueryClusterResponseSerializer(serializers.Serializer):
    class Meta:
        swagger_schema_fields = {"example": []}


class ClusterFilterSerializer(ListResourceSLZ):
    # 基础的集群过滤条件
    bk_biz_id = serializers.IntegerField(help_text=_("业务ID"))
    cluster_ids = serializers.CharField(help_text=_("集群ID(逗号分割)"), required=False, default="")
    cluster_type = serializers.CharField(help_text=_("集群类型"), required=False, default="")

    def validate(self, attrs):
        # 获取集群基础过滤条件用作第一轮过滤
        filters = Q(bk_biz_id=attrs["bk_biz_id"])
        if attrs["cluster_ids"]:
            filters &= Q(id__in=attrs["cluster_ids"].split(","))
        if attrs["cluster_type"]:
            filters &= Q(cluster_type__in=attrs["cluster_type"].split(","))
        attrs["filters"] = filters
        # 补充list resource过滤条件
        query_params = {field: attrs[field] for field in self.fields.keys() if field in attrs}
        attrs["query_params"] = query_params
        return attrs


class ClusterEntryFilterSerializer(ListClusterEntriesSLZ):
    bk_biz_id = serializers.IntegerField(help_text=_("业务ID"))
    cluster_type = serializers.CharField(help_text=_("集群类型"))
    limit = serializers.IntegerField(help_text=_("分页限制"), required=False, default=10)
    offset = serializers.IntegerField(help_text=_("分页起始"), required=False, default=0)


class QueryBizClusterAttrsSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(help_text=_("业务ID"))
    cluster_type = serializers.CharField(help_text=_("集群类型"))
    cluster_attrs = serializers.CharField(help_text=_("查询集群属性字段(逗号分隔)"), default="")
    instances_attrs = serializers.CharField(help_text=_("查询实例属性字段(逗号分隔)"), default="")

    def validate_cluster_type(self, value):
        cluster_types = [ct.strip() for ct in value.split(",")]
        db_type_set = set()
        # 检查特殊case 'redis'
        if all(ct == "redis" for ct in cluster_types):
            return RedisListRetrieveResource.cluster_types
        for cluster_type in cluster_types:
            normalized_type = ClusterType.cluster_type_to_db_type(cluster_type)
            if not normalized_type:
                raise serializers.ValidationError(_("未知的集群类型：{}".format(cluster_type)))
            db_type_set.add(normalized_type)
        if len(db_type_set) > 1:
            raise serializers.ValidationError(_("所有集群类型必须属于同一种DBtype类型"))
        return cluster_types

    def validate(self, attrs):
        attrs["cluster_attrs"] = attrs["cluster_attrs"].split(",") if attrs["cluster_attrs"] else []
        attrs["instances_attrs"] = attrs["instances_attrs"].split(",") if attrs["instances_attrs"] else []
        return attrs


class ResourceAdministrationSerializer(serializers.Serializer):
    resource_type = serializers.ChoiceField(help_text=_("服务类型"), choices=ResourceType.get_choices())

    def to_representation(self, instance):
        resource_type = instance.get("resource_type")
        # 污点主机
        if resource_type == ResourceType.SPOTTY_HOST:
            cloud_info = ResourceQueryHelper.search_cc_cloud(get_cache=True)
            bk_cloud_ids = DirtyMachine.objects.values_list("bk_cloud_id", flat=True).distinct()
            bk_cloud_id_list = [
                {"value": bk_cloud_id, "text": cloud_info.get(str(bk_cloud_id), {}).get("bk_cloud_name", "")}
                for bk_cloud_id in bk_cloud_ids
            ]
            # 业务信息
            biz_infos = CCApi.search_business(
                {
                    "fields": ["bk_biz_id", "bk_biz_name", CC_APP_ABBR_ATTR],
                },
                use_admin=True,
            ).get("info", [])
            # 构建一个以业务ID为键的字典，便于快速查找
            biz_info_dict = {biz_info["bk_biz_id"]: biz_info for biz_info in biz_infos}
            # 从DirtyMachine模型获取去重后的业务ID列表
            bk_biz_ids = list(DirtyMachine.objects.values_list("bk_biz_id", flat=True).distinct())
            # 构建结果列表,直接从字典中查找匹配的业务信息
            bk_biz_id_list = [
                {"value": bk_biz_id, "text": biz_info_dict[bk_biz_id]["bk_biz_name"]}
                for bk_biz_id in bk_biz_ids
                if bk_biz_id in biz_info_dict
            ]
            # 单据类型
            ticket_types = list(DirtyMachine.objects.all().values_list("ticket__ticket_type", flat=True).distinct())
            ticket_types_list = [
                {"value": ticket, "text": TicketType.get_choice_label(ticket)} for ticket in ticket_types
            ]
            resource_attrs = {
                "bk_cloud_id": bk_cloud_id_list,
                "bk_biz_ids": bk_biz_id_list,
                "ticket_types": ticket_types_list,
            }
            return resource_attrs
        elif resource_type == ResourceType.RESOURCE_RECORD:
            # 资源操作记录不需要表头筛选数据,后续这里补充其他表头筛选数据
            return {}


class QueryBizClusterAttrsResponseSerializer(serializers.Serializer):
    class Meta:
        swagger_schema_fields = {"example": {"id": [1, 2, 3], "region": ["sz", "sh"]}}


class WebConsoleSerializer(serializers.Serializer):
    cluster_id = serializers.IntegerField(help_text=_("集群ID"))
    cmd = serializers.CharField(help_text=_("sql语句"))
    # redis 额外参数
    db_num = serializers.IntegerField(help_text=_("数据库编号(redis 额外参数)"), required=False)
    raw = serializers.BooleanField(help_text=_("源编码(redis 额外参数)"), required=False)


class WebConsoleResponseSerializer(serializers.Serializer):
    class Meta:
        swagger_schema_fields = {"example": [{"title1": "xxx", "title2": "xxx"}]}


class ClusterDbTypeSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(help_text=_("业务ID"))
    db_type = serializers.ChoiceField(help_text=_("数据库类型"), choices=DBType.get_choices())


class QueryClusterInstanceCountSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(help_text=_("业务ID"))


class QueryClusterCapSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(help_text=_("业务ID"))
    cluster_type = serializers.CharField(help_text=_("集群类型(多个以逗号分隔)"))


class QueryClusterCapResponseSerializer(serializers.Serializer):
    class Meta:
        swagger_schema_fields = {"example": {"cluster1": {"used": 1, "total": 2, "in_use": 50}}}


class UpdateClusterAliasSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(help_text=_("业务ID"))
    cluster_id = serializers.IntegerField(help_text=_("集群ID"))
    new_alias = serializers.CharField(help_text=_("新集群别名"))

    def validate(self, attrs):
        bk_biz_id = attrs.get("bk_biz_id")
        cluster_id = attrs.get("cluster_id")
        new_alias = attrs.get("new_alias")

        try:
            cluster = Cluster.objects.get(bk_biz_id=bk_biz_id, id=cluster_id)
        except Cluster.DoesNotExist:
            raise serializers.ValidationError(_("Cluster with the given ID does not exist."))

        # 验证新别名不能与原集群名相同
        if cluster.alias == new_alias:
            raise serializers.ValidationError(_("The new alias cannot be the same as the current alias."))

        return attrs
