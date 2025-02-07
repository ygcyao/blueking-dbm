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

import time
from collections import defaultdict
from typing import Dict, List

from django.utils.translation import ugettext_lazy as _
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from backend import env
from backend.bk_web import viewsets
from backend.bk_web.pagination import AuditedLimitOffsetPagination
from backend.bk_web.swagger import common_swagger_auto_schema
from backend.components import CCApi
from backend.components.dbresource.client import DBResourceApi
from backend.components.uwork.client import UWORKApi
from backend.configuration.constants import SystemSettingsEnum
from backend.configuration.models import SystemSettings
from backend.db_meta.models import AppCache
from backend.db_meta.models.machine import DeviceClass
from backend.db_services.dbresource.constants import (
    RESOURCE_IMPORT_EXPIRE_TIME,
    RESOURCE_IMPORT_TASK_FIELD,
    SWAGGER_TAG,
)
from backend.db_services.dbresource.filters import DeviceClassFilter
from backend.db_services.dbresource.handlers import ResourceHandler
from backend.db_services.dbresource.serializers import (
    GetDiskTypeResponseSerializer,
    GetMountPointResponseSerializer,
    ListCvmDeviceClassSerializer,
    ListDBAHostsSerializer,
    ListSubzonesSerializer,
    QueryDBAHostsSerializer,
    QueryOperationListSerializer,
    ResourceApplySerializer,
    ResourceConfirmSerializer,
    ResourceDeleteSerializer,
    ResourceImportResponseSerializer,
    ResourceImportSerializer,
    ResourceListResponseSerializer,
    ResourceListSerializer,
    ResourceSummaryResponseSerializer,
    ResourceSummarySerializer,
    ResourceUpdateSerializer,
    SpecCountResourceResponseSerializer,
    SpecCountResourceSerializer,
    UworkIpsSerializer,
)
from backend.db_services.ipchooser.constants import BK_OS_CODE__TYPE, BkOsType, ModeType
from backend.db_services.ipchooser.handlers.host_handler import HostHandler
from backend.db_services.ipchooser.handlers.topo_handler import TopoHandler
from backend.db_services.ipchooser.query.resource import ResourceQueryHelper
from backend.db_services.ipchooser.types import ScopeList
from backend.flow.consts import FAILED_STATES, SUCCEED_STATES
from backend.flow.engine.controller.base import BaseController
from backend.flow.models import FlowTree
from backend.iam_app.dataclass import ResourceEnum
from backend.iam_app.dataclass.actions import ActionEnum
from backend.iam_app.handlers.drf_perm.base import ResourceActionPermission
from backend.iam_app.handlers.permission import Permission
from backend.ticket.constants import BAMBOO_STATE__TICKET_STATE_MAP, TicketStatus, TicketType
from backend.ticket.models import Ticket
from backend.utils.basic import generate_root_id
from backend.utils.redis import RedisConn


class DBResourceViewSet(viewsets.SystemViewSet):
    action_permission_map = {
        (
            "resource_import",
            "resource_apply",
            "resource_pre_apply",
            "resource_confirm",
            "resource_delete",
            "resource_update",
        ): [ResourceActionPermission([ActionEnum.RESOURCE_POLL_MANAGE])],
        (
            "spec_resource_count",
            "get_mountpoints",
            "get_disktypes",
            "get_subzones",
            "get_device_class",
        ): [],
        ("query_operation_list",): [ResourceActionPermission([ActionEnum.RESOURCE_OPERATION_VIEW])],
    }
    default_permission_class = [ResourceActionPermission([ActionEnum.RESOURCE_MANAGE])]
    filter_class = None
    pagination_class = None

    @common_swagger_auto_schema(
        operation_summary=_("资源池资源列表"),
        request_body=ResourceListSerializer(),
        responses={status.HTTP_200_OK: ResourceListResponseSerializer()},
        tags=[SWAGGER_TAG],
    )
    @action(
        detail=False, methods=["POST"], url_path="list", serializer_class=ResourceListSerializer, pagination_class=None
    )
    @Permission.decorator_external_permission_field(
        param_field=lambda d: None,
        actions=[ActionEnum.RESOURCE_POLL_MANAGE],
        resource_meta=None,
    )
    def resource_list(self, request):
        return Response(ResourceHandler.resource_list(self.params_validate(self.get_serializer_class())))

    @common_swagger_auto_schema(
        operation_summary=_("获取DBA业务下的主机信息"),
        query_serializer=ListDBAHostsSerializer(),
        tags=[SWAGGER_TAG],
    )
    @action(detail=False, methods=["GET"], url_path="list_dba_hosts", serializer_class=ListDBAHostsSerializer)
    def list_dba_hosts(self, request):
        params = self.params_validate(self.get_serializer_class())

        # 查询DBA空闲机模块的meta，构造查询空闲机参数的node_list
        scope_list: ScopeList = [
            {"scope_id": env.DBA_APP_BK_BIZ_ID, "scope_type": "biz", "bk_biz_id": env.DBA_APP_BK_BIZ_ID}
        ]
        trees: List[Dict] = TopoHandler.trees(all_scope=True, mode=ModeType.IDLE_ONLY.value, scope_list=scope_list)
        node_list: ScopeList = [
            {"instance_id": trees[0]["instance_id"], "meta": trees[0]["meta"], "object_id": "module"}
        ]
        params.update(readable_node_list=node_list)

        # 查询DBA业务下的空闲机，并排除掉已经在资源池的空闲机
        resource_hosts = DBResourceApi.resource_list_all()["details"] or []
        resource_host_ids = [host["bk_host_id"] for host in resource_hosts]
        host_infos = TopoHandler.query_hosts(**params)
        for host in host_infos["data"]:
            host.update(occupancy=(host["host_id"] in resource_host_ids))

        return Response(host_infos)

    @common_swagger_auto_schema(
        operation_summary=_("查询DBA业务下的主机信息"),
        query_serializer=QueryDBAHostsSerializer(),
        tags=[SWAGGER_TAG],
    )
    @action(detail=False, methods=["GET"], url_path="query_dba_hosts", serializer_class=QueryDBAHostsSerializer)
    def query_dba_hosts(self, request):
        host_ids = self.params_validate(self.get_serializer_class())["bk_host_ids"].split(",")
        host_list = [{"host_id": int(host_id)} for host_id in host_ids]
        scope_list: ScopeList = [{"bk_biz_id": env.DBA_APP_BK_BIZ_ID}]
        return Response(HostHandler.details(scope_list=scope_list, host_list=host_list))

    @common_swagger_auto_schema(
        operation_summary=_("资源导入"),
        request_body=ResourceImportSerializer(),
        responses={status.HTTP_200_OK: ResourceImportResponseSerializer()},
        tags=[SWAGGER_TAG],
    )
    @action(detail=False, methods=["POST"], url_path="import", serializer_class=ResourceImportSerializer)
    def resource_import(self, request):
        validated_data = self.params_validate(self.get_serializer_class())
        host_ids = [host["host_id"] for host in validated_data.pop("hosts")]

        # 查询主机信息，并按照集群类型聚合
        host_infos = ResourceQueryHelper.search_cc_hosts(role_host_ids=host_ids)
        os_hosts = defaultdict(list)
        for host in host_infos:
            host.update(ip=host["bk_host_innerip"], host_id=host["bk_host_id"])
            os_hosts[host["bk_os_type"]].append(host)

        # 按照集群类型分别导入
        for os_type, hosts in os_hosts.items():
            root_id = generate_root_id()

            # 补充必要的单据参数
            validated_data.update(
                ticket_type=TicketType.RESOURCE_IMPORT,
                created_by=request.user.username,
                uid=None,
                hosts=hosts,
                # 额外补充资源池导入的参数，用于记录操作日志
                bill_id=None,
                bill_type=None,
                task_id=root_id,
                operator=request.user.username,
                os_type=BK_OS_CODE__TYPE[os_type],
            )

            # 资源导入记录
            import_record = {"task_id": root_id, "operator": request.user.username, "hosts": hosts}
            DBResourceApi.import_operation_create(params=import_record)

            # 执行资源导入的后台flow
            validated_data.update(hosts=list(hosts), os_type=BK_OS_CODE__TYPE[os_type])
            BaseController(root_id=root_id, ticket_data=validated_data).import_resource_init_step()

            # 缓存当前任务，并删除过期导入任务
            now = int(time.time())
            cache_key = RESOURCE_IMPORT_TASK_FIELD.format(user=request.user.username)
            RedisConn.zadd(cache_key, {root_id: now})
            expired_tasks = RedisConn.zrangebyscore(cache_key, "-inf", now - RESOURCE_IMPORT_EXPIRE_TIME)
            if expired_tasks:
                RedisConn.zrem(cache_key, *expired_tasks)

        return Response()

    @common_swagger_auto_schema(
        operation_summary=_("查询资源导入任务"),
        tags=[SWAGGER_TAG],
    )
    @action(detail=False, methods=["GET"], url_path="query_import_tasks")
    def query_resource_import_tasks(self, request):
        cache_key = RESOURCE_IMPORT_TASK_FIELD.format(user=request.user.username)
        task_ids = RedisConn.zrange(cache_key, 0, -1)

        # 查询正在进行的task和已经结束的task
        flow_tree_list = FlowTree.objects.filter(root_id__in=task_ids)
        done_tasks, processing_tasks = [], []
        for tree in flow_tree_list:
            if tree.status in [*FAILED_STATES, *SUCCEED_STATES]:
                done_tasks.append(tree.root_id)
            else:
                processing_tasks.append(tree.root_id)

        # 移除已经结束的task
        if done_tasks:
            RedisConn.zrem(cache_key, *done_tasks)

        return Response({"bk_biz_id": env.DBA_APP_BK_BIZ_ID, "task_ids": processing_tasks})

    @common_swagger_auto_schema(
        operation_summary=_("资源申请"),
        request_body=ResourceApplySerializer(),
        tags=[SWAGGER_TAG],
    )
    @action(detail=False, methods=["POST"], url_path="apply", serializer_class=ResourceApplySerializer)
    def resource_apply(self, request):
        validated_data = self.params_validate(self.get_serializer_class())
        return Response(DBResourceApi.resource_apply(params=validated_data))

    @common_swagger_auto_schema(
        operation_summary=_("获取挂载点"),
        responses={status.HTTP_200_OK: GetMountPointResponseSerializer()},
        tags=[SWAGGER_TAG],
    )
    @action(detail=False, methods=["GET"])
    def get_mountpoints(self, request):
        return Response(DBResourceApi.get_mountpoints())

    @common_swagger_auto_schema(
        operation_summary=_("获取磁盘类型"),
        responses={status.HTTP_200_OK: GetDiskTypeResponseSerializer()},
        tags=[SWAGGER_TAG],
    )
    @action(detail=False, methods=["GET"])
    def get_disktypes(self, request):
        return Response(DBResourceApi.get_disktypes())

    @common_swagger_auto_schema(
        operation_summary=_("获取操作系统类型"),
        tags=[SWAGGER_TAG],
    )
    @action(detail=False, methods=["GET"])
    def get_os_types(self, request):
        return Response(BkOsType.get_values())

    @common_swagger_auto_schema(
        operation_summary=_("根据逻辑城市查询园区"),
        query_serializer=ListSubzonesSerializer(),
        tags=[SWAGGER_TAG],
    )
    @action(detail=False, methods=["GET"], serializer_class=ListSubzonesSerializer)
    def get_subzones(self, request):
        validated_data = self.params_validate(self.get_serializer_class())
        return Response(DBResourceApi.get_subzones(validated_data))

    @common_swagger_auto_schema(
        operation_summary=_("获取机型列表"),
        tags=[SWAGGER_TAG],
    )
    @action(
        detail=False,
        methods=["GET"],
        serializer_class=ListCvmDeviceClassSerializer,
        filter_class=DeviceClassFilter,
        pagination_class=AuditedLimitOffsetPagination,
        queryset=DeviceClass.objects.all(),
    )
    def get_device_class(self, request):
        page_device_qs = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        page_device_data = self.serializer_class(instance=page_device_qs, many=True).data
        return self.paginator.get_paginated_response(data=page_device_data)

    @common_swagger_auto_schema(
        operation_summary=_("资源预申请"),
        request_body=ResourceApplySerializer(),
        tags=[SWAGGER_TAG],
    )
    @action(detail=False, methods=["POST"], url_path="pre_apply", serializer_class=ResourceApplySerializer)
    def resource_pre_apply(self, request):
        validated_data = self.params_validate(self.get_serializer_class())
        resp = DBResourceApi.resource_pre_apply(params=validated_data, raw=True)
        resp["resource_request_id"] = resp["request_id"]
        return Response(resp)

    @common_swagger_auto_schema(
        operation_summary=_("资源确认"),
        request_body=ResourceConfirmSerializer(),
        tags=[SWAGGER_TAG],
    )
    @action(detail=False, methods=["POST"], url_path="confirm", serializer_class=ResourceConfirmSerializer)
    def resource_confirm(self, request):
        validated_data = self.params_validate(self.get_serializer_class())
        return Response(DBResourceApi.resource_confirm(params=validated_data))

    @common_swagger_auto_schema(
        operation_summary=_("资源删除"),
        request_body=ResourceDeleteSerializer(),
        tags=[SWAGGER_TAG],
    )
    @action(detail=False, methods=["POST"], url_path="delete", serializer_class=ResourceDeleteSerializer)
    def resource_delete(self, request):
        validated_data = self.params_validate(self.get_serializer_class())
        # 从资源池删除机器
        resp = DBResourceApi.resource_delete(params=validated_data)
        # 将在资源池模块的机器移到空闲机，若机器处于其他模块，则忽略
        move_idle_hosts: List[int] = []
        resource_topo = SystemSettings.get_setting_value(key=SystemSettingsEnum.MANAGE_TOPO.value)
        for topo in CCApi.find_host_biz_relations({"bk_host_id": validated_data["bk_host_ids"]}):
            if (
                topo["bk_set_id"] == resource_topo["set_id"]
                and topo["bk_module_id"] == resource_topo["resource_module_id"]
            ):
                move_idle_hosts.append(topo["bk_host_id"])

        if move_idle_hosts:
            CCApi.transfer_host_to_idlemodule({"bk_biz_id": env.DBA_APP_BK_BIZ_ID, "bk_host_id": move_idle_hosts})

        return Response(resp)

    @common_swagger_auto_schema(
        operation_summary=_("资源更新"),
        request_body=ResourceUpdateSerializer(),
        tags=[SWAGGER_TAG],
    )
    @action(detail=False, methods=["POST"], url_path="update", serializer_class=ResourceUpdateSerializer)
    def resource_update(self, request):
        update_params = self.params_validate(self.get_serializer_class())
        return Response(DBResourceApi.resource_batch_update(params=update_params))

    @common_swagger_auto_schema(
        operation_summary=_("按照组件统计资源数量"),
        tags=[SWAGGER_TAG],
    )
    @action(detail=False, methods=["GET"])
    def resource_group_count(self, request):
        return Response(DBResourceApi.resource_group_count())

    @common_swagger_auto_schema(
        operation_summary=_("按照条件聚合资源统计"),
        query_serializer=ResourceSummarySerializer(),
        responses={status.HTTP_200_OK: ResourceSummaryResponseSerializer()},
        tags=[SWAGGER_TAG],
    )
    @action(methods=["GET"], detail=False, serializer_class=ResourceSummarySerializer)
    def resource_summary(self, request):
        group_params = self.params_validate(self.get_serializer_class())
        summary_data = DBResourceApi.resource_summary(params=group_params)
        # 补充业务名
        for_biz_ids = [data["dedicated_biz"] for data in summary_data]
        for_biz_infos = AppCache.batch_get_app_attr(bk_biz_ids=for_biz_ids, attr_name="bk_biz_name")
        summary_data = [{"for_biz_name": for_biz_infos.get(data["dedicated_biz"]), **data} for data in summary_data]
        return Response(summary_data)

    @common_swagger_auto_schema(
        operation_summary=_("获取资源导入相关链接"),
        tags=[SWAGGER_TAG],
    )
    @action(detail=False, methods=["GET"], url_path="resource_import_urls")
    def resource_import_urls(self, request):
        return Response(
            {"bk_cmdb_url": env.BK_CMDB_URL, "bk_nodeman_url": env.BK_NODEMAN_URL, "bk_scr_url": env.BK_SCR_URL}
        )

    @common_swagger_auto_schema(
        operation_summary=_("查询资源操作记录"),
        query_serializer=QueryOperationListSerializer(),
        tags=[SWAGGER_TAG],
    )
    @action(
        detail=False,
        methods=["GET"],
        url_path="query_operation_list",
        serializer_class=QueryOperationListSerializer,
        pagination_class=None,
    )
    @Permission.decorator_permission_field(
        id_field=lambda d: d["task_id"],
        data_field=lambda d: d["results"],
        actions=[ActionEnum.FLOW_DETAIL],
        resource_meta=ResourceEnum.TASKFLOW,
    )
    @Permission.decorator_permission_field(
        id_field=lambda d: d["ticket_id"],
        data_field=lambda d: d["results"],
        actions=[ActionEnum.TICKET_VIEW],
        resource_meta=ResourceEnum.TICKET,
    )
    def query_operation_list(self, request):
        query_params = self.params_validate(self.get_serializer_class())
        operation_list = DBResourceApi.operation_list(query_params)
        operation_list["results"] = operation_list.pop("details") or []

        task_ids: List[int] = [op["task_id"] for op in operation_list["results"]]
        task_id__task: Dict[int, Ticket] = {
            task.root_id: task for task in FlowTree.objects.filter(root_id__in=task_ids)
        }
        for op in operation_list["results"]:
            # 格式化操作记录参数
            op["ticket_id"] = int(op.pop("bill_id") or 0)
            op["ticket_type"] = op.pop("bill_type", "")
            op["ticket_type_display"] = TicketType.get_choice_label(op["ticket_type"])
            op["bk_biz_id"] = getattr(task_id__task.get(op["task_id"]), "bk_biz_id", env.DBA_APP_BK_BIZ_ID)
            task_status = getattr(task_id__task.get(op["task_id"]), "status", "")
            op["status"] = BAMBOO_STATE__TICKET_STATE_MAP.get(task_status, TicketStatus.RUNNING)

        # 过滤单据状态的操作记录
        operation_list["results"] = [
            op
            for op in operation_list["results"]
            if not query_params.get("status") or op["status"] == query_params["status"]
        ]

        return Response(operation_list)

    @common_swagger_auto_schema(
        operation_summary=_("规格数量的预计"),
        request_body=SpecCountResourceSerializer(),
        responses={status.HTTP_200_OK: SpecCountResourceResponseSerializer()},
        tags=[SWAGGER_TAG],
    )
    @action(
        detail=False,
        methods=["POST"],
        url_path="spec_resource_count",
        serializer_class=SpecCountResourceSerializer,
        pagination_class=None,
    )
    def spec_resource_count(self, request):
        apply_params = self.params_validate(self.get_serializer_class())
        return Response(ResourceHandler.spec_resource_count(**apply_params))

    @common_swagger_auto_schema(
        operation_summary=_("查询故障主机信息"),
        query_serializer=UworkIpsSerializer(),
        tags=[SWAGGER_TAG],
    )
    @action(detail=False, methods=["GET"], serializer_class=UworkIpsSerializer)
    def check_uwork_ips(self, request):
        if not env.UWORK_APIGW_DOMAIN:
            return Response({"results": []})
        ip_list = self.params_validate(self.get_serializer_class())["ips"]
        results = UWORKApi.uwork_list(params={"serverIpList": ip_list})
        uwork_list = [result["serverIp"] for result in results]
        return Response({"results": uwork_list})
