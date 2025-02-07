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
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view
from rest_framework.request import Request

from backend.db_meta import api
from backend.db_meta.enums import ClusterType


# sqlserver_single
@swagger_auto_schema(methods=["get"])
@csrf_exempt
# @login_exempt
@api_view(["GET"])
# @permission_classes([AllowAny])
def sqlserver_single_cluster_instances(request: Request):
    try:
        return JsonResponse(
            {
                "msg": "",
                "code": 0,
                "data": api.priv_manager.sqlserver.cluster_instances(
                    entry_name=request.query_params.get("entry_name"),
                    cluster_type=ClusterType.SqlserverSingle.value,
                ),
            }
        )
    except Exception as e:
        return JsonResponse({"msg": "{}".format(e), "code": 1, "data": ""})


# sqlserver_single
@swagger_auto_schema(methods=["get"])
@csrf_exempt
# @login_exempt
@api_view(["GET"])
# @permission_classes([AllowAny])
def sqlserver_ha_cluster_instances(request: Request):
    try:
        return JsonResponse(
            {
                "msg": "",
                "code": 0,
                "data": api.priv_manager.sqlserver.cluster_instances(
                    entry_name=request.query_params.get("entry_name"),
                    cluster_type=ClusterType.SqlserverHA.value,
                ),
            }
        )
    except Exception as e:
        return JsonResponse({"msg": "{}".format(e), "code": 1, "data": ""})


@swagger_auto_schema(methods=["get"])
@csrf_exempt
@api_view(["GET"])
def biz_clusters(request: Request):
    try:
        return JsonResponse(
            {
                "msg": "",
                "code": 0,
                "data": api.priv_manager.biz_clusters(
                    bk_biz_id=request.query_params.get("bk_biz_id"),
                    immute_domains=request.query_params.getlist("immute_domains"),
                ),
            }
        )
    except Exception as e:  # pylint: disable=broad-except
        return JsonResponse({"msg": "{}".format(e), "code": 1, "data": ""})
