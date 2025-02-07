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
import copy
import logging
from unittest.mock import PropertyMock, patch

import pytest
from bamboo_engine.api import EngineAPIResult
from bamboo_engine.states import StateType
from django.conf import settings
from pipeline.eri.signals import post_set_state
from rest_framework.permissions import AllowAny
from rest_framework.test import APIClient

from backend.db_meta.models import AppCache, Cluster, Machine, ProxyInstance, Spec
from backend.flow.engine.bamboo.engine import BambooEngine
from backend.flow.models import FlowTree
from backend.tests.mock_data.components.cc import CCApiMock
from backend.tests.mock_data.components.itsm import ItsmApiMock
from backend.tests.mock_data.iam_app.permission import PermissionMock
from backend.tests.mock_data.ticket.mongodb_flow import (
    APPCACHE_DATA,
    BK_BIZ_ID,
    BK_USERNAME,
    MANGODB_ADD_MANGOS_TICKET_DATA,
    MANGODB_CLUSTER_DATA,
    MANGODB_CUTOFF_TICKET_DATA,
    MANGODB_DESTROY_TICKET_DATA,
    MANGODB_MACHINE_DATA,
    MANGODB_PROXYINSTANCE_DATA,
    MANGODB_REDUCE_MANGOS_DATA,
    MANGODB_SOURCE_APPLICATION_DATA,
    MANGODB_SPEC_DATA,
    MANGOS_ADD_SOURCE_DATA,
    MONGODB_REMOVE_NS_TICKET_DATA,
)
from backend.tests.mock_data.ticket.ticket_flow import ROOT_ID, SN, SQL_IMPORT_NODE_ID, SQL_IMPORT_VERSION_ID
from backend.ticket.constants import FlowType, TicketFlowStatus, TicketStatus, TicketType, TodoType
from backend.ticket.flow_manager.inner import InnerFlow
from backend.ticket.flow_manager.pause import PauseFlow
from backend.ticket.models import Flow
from backend.ticket.views import TicketViewSet

logger = logging.getLogger("test")
pytestmark = pytest.mark.django_db
client = APIClient()

INITIAL_FLOW_FINISHED_STATUS = [TicketFlowStatus.SKIPPED, TicketFlowStatus.SUCCEEDED]
CHANGED_MOCK_STATUS = [TicketFlowStatus.SKIPPED, TicketStatus.SUCCEEDED, TicketFlowStatus.RUNNING]


@pytest.fixture(scope="function")
def query_fixture(django_db_blocker):
    with django_db_blocker.unblock():
        # 初始化集群数据
        Spec.objects.all().delete()
        Cluster.objects.create(**MANGODB_CLUSTER_DATA)
        AppCache.objects.create(**APPCACHE_DATA)
        Spec.objects.bulk_create([Spec(**data) for data in MANGODB_SPEC_DATA])
        Machine.objects.bulk_create([Machine(**data) for data in MANGODB_MACHINE_DATA])
        ProxyInstance.objects.bulk_create([ProxyInstance(**data) for data in MANGODB_PROXYINSTANCE_DATA])
        cluster_id = Cluster.objects.first()
        for proxy_instance in ProxyInstance.objects.all():
            proxy_instance.cluster.add(cluster_id)

        yield
        ProxyInstance.objects.all().delete()
        Cluster.objects.all().delete()
        AppCache.objects.all().delete()
        Spec.objects.all().delete()
        Machine.objects.all().delete()


@pytest.fixture(autouse=True)  # autouse=True 会自动应用这个fixture到所有的测试中
def set_empty_middleware():
    with patch.object(settings, "MIDDLEWARE", []):
        yield


class TestMangodbFlow:
    """
    mangodb测试类
    """

    # mangos 扩容接入层
    @patch.object(TicketViewSet, "permission_classes")
    @patch.object(InnerFlow, "_run")
    @patch.object(InnerFlow, "status", new_callable=PropertyMock)
    @patch.object(PauseFlow, "status", new_callable=PropertyMock)
    @patch.object(TicketViewSet, "get_permissions", lambda x: [])
    @patch("backend.ticket.flow_manager.itsm.ItsmApi", ItsmApiMock())
    @patch("backend.db_services.cmdb.biz.CCApi", CCApiMock())
    @patch("backend.core.notify.send_msg.apply_async", lambda *args, **kwargs: "有一条MANGOS 扩容接入层待办需要您处理")
    @patch(
        "backend.ticket.flow_manager.resource.ResourceApplyFlow.apply_resource",
        lambda resource_request_id, node_infos: (1, MANGOS_ADD_SOURCE_DATA),
    )
    @patch("backend.db_services.cmdb.biz.Permission", PermissionMock)
    def test_mango_add_mangos_flow(
        self, mock_pause_status, mocked_status, mocked__run, mocked_permission_classes, query_fixture, db
    ):
        # MANGODB 扩容接入层: start --> itsm --> PAUSE --> RESOURC --> INNER_FLOW --> end
        mocked_status.return_value = TicketStatus.SUCCEEDED
        mock_pause_status.return_value = TicketFlowStatus.SKIPPED
        mocked__run.return_value = ROOT_ID
        mocked_permission_classes.return_value = [AllowAny]

        client.login(username="admin")

        # itsm流程
        mangos_add_data = copy.deepcopy(MANGODB_ADD_MANGOS_TICKET_DATA)
        client.post("/apis/tickets/", data=mangos_add_data)
        current_flow = Flow.objects.filter(flow_obj_id=SN).first()
        assert current_flow is not None

        # PAUSE流程
        client.post(f"/apis/tickets/{current_flow.ticket_id}/callback/")
        current_flow = Flow.objects.exclude(flow_obj_id="").last()
        assert current_flow.flow_type == FlowType.PAUSE
        # RESOURCE_APPLY -> INNER_FLOW
        client.post(f"/apis/tickets/{current_flow.ticket_id}/callback/")
        current_flow = Flow.objects.exclude(flow_obj_id="").last()
        assert current_flow.flow_type == FlowType.INNER_FLOW

    # mangos 缩容接入层
    @patch.object(TicketViewSet, "permission_classes")
    @patch.object(InnerFlow, "_run")
    @patch.object(InnerFlow, "status", new_callable=PropertyMock)
    @patch.object(PauseFlow, "status", new_callable=PropertyMock)
    @patch.object(TicketViewSet, "get_permissions", lambda x: [])
    @patch("backend.ticket.flow_manager.itsm.ItsmApi", ItsmApiMock())
    @patch("backend.db_services.cmdb.biz.CCApi", CCApiMock())
    @patch("backend.core.notify.send_msg.apply_async", lambda *args, **kwargs: "有一条MANGOS 缩容接入层待办需要您处理")
    @patch("backend.db_services.cmdb.biz.Permission", PermissionMock)
    def test_mango_reduce_mangos_flow(
        self, mock_pause_status, mocked_status, mocked__run, mocked_permission_classes, query_fixture, db
    ):
        # MANGOS 缩容接入层: start --> itsm --> PAUSE --> INNER_FLOW --> end
        mocked_status.return_value = TicketStatus.SUCCEEDED
        mock_pause_status.return_value = TicketFlowStatus.SKIPPED
        mocked__run.return_value = ROOT_ID
        mocked_permission_classes.return_value = [AllowAny]

        client.login(username="admin")

        # itsm流程
        mangos_add_data = copy.deepcopy(MANGODB_REDUCE_MANGOS_DATA)
        client.post("/apis/tickets/", data=mangos_add_data)
        current_flow = Flow.objects.filter(flow_obj_id=SN).first()
        assert current_flow is not None

        # PAUSE流程
        client.post(f"/apis/tickets/{current_flow.ticket_id}/callback/")
        current_flow = Flow.objects.exclude(flow_obj_id="").last()
        assert current_flow.flow_type == FlowType.PAUSE
        # RESOURCE_APPLY -> INNER_FLOW
        client.post(f"/apis/tickets/{current_flow.ticket_id}/callback/")
        current_flow = Flow.objects.exclude(flow_obj_id="").last()
        assert current_flow.flow_type == FlowType.INNER_FLOW

    @patch.object(TicketViewSet, "permission_classes")
    @patch.object(InnerFlow, "_run")
    @patch.object(InnerFlow, "status", new_callable=PropertyMock)
    @patch.object(PauseFlow, "status", new_callable=PropertyMock)
    @patch.object(TicketViewSet, "get_permissions", lambda x: [])
    @patch("backend.ticket.flow_manager.itsm.ItsmApi", ItsmApiMock())
    @patch("backend.db_services.cmdb.biz.CCApi", CCApiMock())
    @patch("backend.core.notify.send_msg.apply_async", lambda *args, **kwargs: "有一条MANGODB 集群下架待办需要您处理")
    @patch("backend.db_services.cmdb.biz.Permission", PermissionMock)
    def test_mangodb_destroy_flow(
        self, mock_pause_status, mocked_status, mocked__run, mocked_permission_classes, query_fixture, db
    ):
        # MANGODB 集群下架: start --> itsm --> PAUSE --> INNER_FLOW --> end
        mocked_status.return_value = TicketStatus.SUCCEEDED
        mock_pause_status.return_value = TicketFlowStatus.SKIPPED
        mocked__run.return_value = ROOT_ID
        mocked_permission_classes.return_value = [AllowAny]

        client.login(username="admin")

        # itsm流程
        mangos_add_data = copy.deepcopy(MANGODB_DESTROY_TICKET_DATA)
        client.post("/apis/tickets/", data=mangos_add_data)
        current_flow = Flow.objects.filter(flow_obj_id=SN).first()
        assert current_flow is not None

        # PAUSE流程
        client.post(f"/apis/tickets/{current_flow.ticket_id}/callback/")
        current_flow = Flow.objects.exclude(flow_obj_id="").last()
        assert current_flow.flow_type == FlowType.PAUSE
        # RESOURCE_APPLY -> INNER_FLOW
        client.post(f"/apis/tickets/{current_flow.ticket_id}/callback/")
        current_flow = Flow.objects.exclude(flow_obj_id="").last()
        assert current_flow.flow_type == FlowType.INNER_FLOW

    @patch.object(TicketViewSet, "permission_classes")
    @patch.object(InnerFlow, "_run")
    @patch.object(InnerFlow, "status", new_callable=PropertyMock)
    @patch.object(PauseFlow, "status", new_callable=PropertyMock)
    @patch.object(TicketViewSet, "get_permissions", lambda x: [])
    @patch("backend.ticket.flow_manager.itsm.ItsmApi", ItsmApiMock())
    @patch("backend.db_services.cmdb.biz.CCApi", CCApiMock())
    @patch("backend.core.notify.send_msg.apply_async", lambda *args, **kwargs: "有一条MANGO 整机替换待办需要您处理")
    @patch(
        "backend.ticket.flow_manager.resource.ResourceApplyFlow.apply_resource",
        lambda resource_request_id, node_infos: (1, MANGODB_SOURCE_APPLICATION_DATA),
    )
    @patch("backend.db_services.cmdb.biz.Permission", PermissionMock)
    def test_mango_outoff_flow(
        self, mock_pause_status, mocked_status, mocked__run, mocked_permission_classes, query_fixture, db
    ):
        # MANGODB 整机替换: start --> itsm --> PAUSE --> RESOURC --> INNER_FLOW --> end
        mocked_status.return_value = TicketStatus.SUCCEEDED
        mock_pause_status.return_value = TicketFlowStatus.SKIPPED
        mocked__run.return_value = ROOT_ID
        mocked_permission_classes.return_value = [AllowAny]

        client.login(username="admin")

        # itsm流程
        mangos_add_data = copy.deepcopy(MANGODB_CUTOFF_TICKET_DATA)
        client.post("/apis/tickets/", data=mangos_add_data)
        current_flow = Flow.objects.filter(flow_obj_id=SN).first()
        assert current_flow is not None

        # PAUSE流程
        client.post(f"/apis/tickets/{current_flow.ticket_id}/callback/")
        current_flow = Flow.objects.exclude(flow_obj_id="").last()
        assert current_flow.flow_type == FlowType.PAUSE
        # RESOURCE_APPLY -> INNER_FLOW
        client.post(f"/apis/tickets/{current_flow.ticket_id}/callback/")
        current_flow = Flow.objects.exclude(flow_obj_id="").last()
        assert current_flow.flow_type == FlowType.INNER_FLOW

    @pytest.mark.skip()
    @patch.object(TicketViewSet, "permission_classes")
    @patch.object(BambooEngine, "get_pipeline_states")
    @patch.object(InnerFlow, "_run")
    @patch.object(PauseFlow, "status", new_callable=PropertyMock)
    @patch.object(TicketViewSet, "get_permissions", lambda x: [])
    @patch("backend.ticket.flow_manager.itsm.ItsmApi", ItsmApiMock())
    @patch("backend.db_services.cmdb.biz.CCApi", CCApiMock())
    @patch("backend.core.notify.send_msg.apply_async", lambda *args, **kwargs: "有一条MONGODB 集群清档待办需要您处理")
    @patch("backend.db_services.cmdb.biz.Permission", PermissionMock)
    def test_mongo_remove_ns(
        self,
        mock_pause_status,
        mocked__run,
        mocked_pipeline_states,
        mocked_permission_classes,
        query_fixture,
        db,
    ):
        """
            mongo清档
        :return:
        """
        # start --> itsm --> PAUSE --> INNER_FLOW --> end
        mock_pause_status.return_value = TicketFlowStatus.SUCCEEDED
        mocked__run.return_value = ROOT_ID
        mocked_permission_classes.return_value = [AllowAny]

        client.login(username="admin")

        # itsm流程
        create_ticket_data = copy.deepcopy(MONGODB_REMOVE_NS_TICKET_DATA)
        client.post("/apis/tickets/", data=create_ticket_data)
        current_flow = Flow.objects.filter(flow_obj_id=SN).first()
        assert current_flow is not None
        # PAUSE流程
        client.post(f"/apis/tickets/{current_flow.ticket_id}/callback/")
        current_flow = Flow.objects.filter(ticket=current_flow.ticket, flow_type=FlowType.PAUSE).first()
        assert current_flow.status == TicketFlowStatus.RUNNING
        # process_todo
        todo = current_flow.todo_of_flow.first()
        process_todo_data = {
            "action": TodoType.APPROVE,
            "todo_id": todo.id,
            "ticket_id": current_flow.ticket.id,
            "params": {},
        }
        client.post(f"/apis/tickets/{current_flow.ticket_id}/process_todo/", data=process_todo_data)
        current_flow = Flow.objects.filter(ticket=current_flow.ticket, flow_type=FlowType.INNER_FLOW).first()

        mocked_pipeline_states.return_value = EngineAPIResult(
            **{
                "result": True,
                "message": "success",
                "exc": None,
                "data": {current_flow.flow_obj_id: {"state": StateType.FINISHED.value}},
                "exc_trace": None,
            }
        )

        flow_tree_data = {
            "bk_biz_id": BK_BIZ_ID,
            "uid": current_flow.ticket.id,
            "ticket_type": TicketType.MONGODB_REMOVE_NS.value,
            "root_id": current_flow.flow_obj_id,
            "tree": {"activities": {"SQL_IMPORT_NODE_ID": {"component": {"code": 1}}}},
            "status": StateType.RUNNING.value,
            "created_by": BK_USERNAME,
        }
        FlowTree.objects.create(**flow_tree_data)

        signal_handler_params = {
            "node_id": SQL_IMPORT_NODE_ID,
            "to_state": StateType.FINISHED.value,
            "version": SQL_IMPORT_VERSION_ID,
            "root_id": current_flow.flow_obj_id,
        }
        # 手动触发信号
        post_set_state.send(sender=Flow, instance=current_flow, state="new_state", **signal_handler_params)

        current_flow = Flow.objects.filter(ticket=current_flow.ticket, flow_type=FlowType.INNER_FLOW).first()
        assert current_flow.status == TicketFlowStatus.SUCCEEDED
