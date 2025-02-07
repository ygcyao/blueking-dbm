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
from datetime import datetime
from typing import Any, Union

from django.utils.translation import gettext as _

from backend.components import ItsmApi
from backend.components.itsm.constants import ItsmTicketStatus
from backend.exceptions import ApiResultError
from backend.ticket.constants import TicketFlowStatus, TicketStatus, TodoStatus, TodoType
from backend.ticket.flow_manager.base import BaseTicketFlow
from backend.ticket.models import Flow, Todo
from backend.ticket.todos.itsm_todo import ItsmTodoContext
from backend.utils.time import datetime2str, standardized_time_str


class ItsmFlow(BaseTicketFlow):
    def __init__(self, flow_obj: Flow):
        super().__init__(flow_obj=flow_obj)

    @property
    def ticket_approval_result(self):
        # 优先读取缓存，避免同一个对象内多次请求 ITSM
        if getattr(self, "_ticket_approval_result", None):
            return self._ticket_approval_result

        # 调用ITSM接口查询审批状态
        try:
            data = ItsmApi.ticket_approval_result({"sn": [self.flow_obj.flow_obj_id]}, use_admin=True)
            itsm_ticket_result = data[0]
        except (IndexError, ApiResultError):
            itsm_ticket_result = None

        setattr(self, "_ticket_approval_result", itsm_ticket_result)
        return itsm_ticket_result

    @property
    def ticket_logs(self):
        # 同ticket_approval_result，优先读取缓存
        if getattr(self, "_ticket_logs", None):
            return self._ticket_logs

        try:
            itsm_logs = ItsmApi.get_ticket_logs({"sn": [self.flow_obj.flow_obj_id]}, use_admin=True)
            ticket_logs = itsm_logs["logs"]
        except (KeyError, ApiResultError):
            ticket_logs = []

        setattr(self, "_ticket_logs", ticket_logs)
        return ticket_logs

    @property
    def _start_time(self) -> str:
        return datetime2str(self.flow_obj.create_at)

    @property
    def _end_time(self) -> Union[datetime, Any]:
        if self.ticket_approval_result:
            return standardized_time_str(self.ticket_approval_result["update_at"])

        return self.flow_obj.update_at

    @property
    def _summary(self) -> dict:
        # 获取单据审批状态
        current_status = self.ticket_approval_result["current_status"]
        approve_result = self.ticket_approval_result["approve_result"]
        summary = {"status": current_status, "approve_result": approve_result}

        # 目前审批流程是固定的，取流程中第三个节点的日志作为概览即可
        try:
            summary.update(operator=self.ticket_logs[2]["operator"], message=self.ticket_logs[2]["message"])
        except (IndexError, KeyError):
            # 异常时根据状态取默认的概览
            msg = TicketStatus.get_choice_label(self.status)
            summary.update(operator=self.ticket_logs[-1]["operator"], status=self.status, message=msg)
        return summary

    @property
    def _status(self) -> str:
        # 把 ITSM 单据状态映射为本系统内的单据状态
        current_status = self.ticket_approval_result["current_status"]
        approve_result = self.ticket_approval_result["approve_result"]

        # 进行中
        if current_status == ItsmTicketStatus.RUNNING:
            return self.flow_obj.update_status(TicketFlowStatus.RUNNING)

        todo = self.flow_obj.todo_of_flow.first()
        # 非进行中的单据，肯定已经来到了第三个节点，否则也无法处理todo
        updater = self.ticket_logs[2]["operator"]
        # 撤单
        if current_status == ItsmTicketStatus.REVOKED:
            todo.set_status(username=updater, status=TodoStatus.DONE_FAILED)
            return self.flow_obj.update_status(TicketFlowStatus.TERMINATED)
        # 审批通过
        elif current_status == ItsmTicketStatus.FINISHED and approve_result:
            todo.set_status(username=updater, status=TodoStatus.DONE_SUCCESS)
            return self.flow_obj.update_status(TicketFlowStatus.SUCCEEDED)
        # 审批拒绝
        elif current_status == ItsmTicketStatus.FINISHED and not approve_result:
            todo.set_status(username=updater, status=TodoStatus.DONE_FAILED)
            return self.flow_obj.update_status(TicketFlowStatus.TERMINATED)
        # 终止
        elif current_status == ItsmTicketStatus.TERMINATED:
            todo.set_status(username=updater, status=TodoStatus.DONE_FAILED)
            return self.flow_obj.update_status(TicketFlowStatus.TERMINATED)

    @property
    def _url(self) -> str:
        if self.ticket_approval_result:
            return self.ticket_approval_result["ticket_url"]

        return ""

    def _run(self) -> str:
        Todo.objects.create(
            name=_("【{}】单据等待审批").format(self.ticket.get_ticket_type_display()),
            flow=self.flow_obj,
            ticket=self.ticket,
            type=TodoType.ITSM,
            context=ItsmTodoContext(self.flow_obj.id, self.ticket.id).to_dict(),
        )
        # 创建单据
        data = ItsmApi.create_ticket(self.flow_obj.details)
        return data["sn"]

    def _revoke(self, operator) -> Any:
        # 父类通过触发todo的终止可以终止itsm单据
        super()._revoke(operator)
