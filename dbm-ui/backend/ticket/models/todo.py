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
import logging

from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from backend import env
from backend.bk_web.constants import LEN_MIDDLE, LEN_SHORT
from backend.bk_web.models import AuditedModel
from backend.configuration.models import BizSettings, DBAdministrator
from backend.ticket.builders import BuilderFactory
from backend.ticket.constants import TODO_RUNNING_STATUS, TicketFlowStatus, TodoStatus, TodoType

logger = logging.getLogger("root")


class TodoManager(models.Manager):
    def exist_unfinished(self):
        return self.filter(status__in=TODO_RUNNING_STATUS).exists()

    def get_operators(self, todo_type, ticket, operators):
        # 获得提单人，dba，业务协助人. TODO: 后续还会细分主、备、二线DBA，以及明确区分协助人角色
        creator = [ticket.creator]
        # dba = DBAdministrator.get_biz_db_type_admins(ticket.bk_biz_id, ticket.group)
        dba, second_dba, other_dba = DBAdministrator.get_dba_for_db_type(ticket.bk_biz_id, ticket.group)
        biz_helpers = BizSettings.get_assistance(ticket.bk_biz_id)

        # 构造单据状态与处理人之间的对应关系
        # - 审批中：提单人可撤销，dba可处理，
        #   考虑某些单据审批人是特定配置(数据导出 -- 运维审批)，所以从ItsmBuilder获得审批人
        # - 待执行：operators[提单人] + helpers[单据协助人]
        # - 待继续：operators[提单人 + dba] + helpers[单据协助人 + second_dba + other_dba]
        # - 待补货：operators[提单人 + dba] + helpers[单据协助人 + second_dba + other_dba]
        # - 已失败：operators[提单人 + dba] + helpers[单据协助人 + second_dba + other_dba]
        itsm_builder = BuilderFactory.get_builder_cls(ticket.ticket_type).itsm_flow_builder(ticket)
        itsm_operators = itsm_builder.get_approvers().split(",")
        todo_operators_map = {
            TodoType.ITSM: itsm_operators[:1],
            TodoType.APPROVE: creator,
            TodoType.INNER_APPROVE: creator + dba,
            TodoType.RESOURCE_REPLENISH: creator + dba,
            TodoType.INNER_FAILED: creator + dba,
        }
        todo_helpers_map = {
            TodoType.ITSM: itsm_operators[1:],
            TodoType.APPROVE: biz_helpers,
            TodoType.INNER_APPROVE: biz_helpers + second_dba + other_dba,
            TodoType.RESOURCE_REPLENISH: biz_helpers + second_dba + other_dba,
            TodoType.INNER_FAILED: biz_helpers + second_dba + other_dba,
        }
        # 按照顺序去重
        operators = list(dict.fromkeys(operators + todo_operators_map.get(todo_type, [])))
        helpers = [item for item in todo_helpers_map.get(todo_type, []) if item not in operators]
        return creator, biz_helpers, helpers, operators

    def create(self, **kwargs):
        creator, biz_helpers, helpers, operators = self.get_operators(
            kwargs["type"], kwargs["ticket"], kwargs.get("operators", [])
        )
        kwargs["operators"] = operators
        kwargs["helpers"] = helpers
        todo = super().create(**kwargs)
        return todo


class Todo(AuditedModel):
    """
    Flow相关的待办
    """

    name = models.CharField(_("待办标题"), max_length=LEN_MIDDLE, default="")
    flow = models.ForeignKey("Flow", help_text=_("关联流程任务"), related_name="todo_of_flow", on_delete=models.CASCADE)
    ticket = models.ForeignKey("Ticket", help_text=_("关联工单"), related_name="todo_of_ticket", on_delete=models.CASCADE)
    operators = models.JSONField(_("待办人"), default=list)
    helpers = models.JSONField(_("协助人"), default=list)
    type = models.CharField(
        _("待办类型"),
        choices=TodoType.get_choices(),
        max_length=LEN_SHORT,
        default=TodoType.APPROVE,
    )
    context = models.JSONField(_("上下文"), default=dict)
    status = models.CharField(
        _("待办状态"),
        choices=TodoStatus.get_choices(),
        max_length=LEN_SHORT,
        default=TodoStatus.TODO,
    )
    done_by = models.CharField(_("待办完成人"), max_length=LEN_SHORT, default="")
    done_at = models.DateTimeField(_("待办完成时间"), null=True)

    objects = TodoManager()

    class Meta:
        verbose_name_plural = verbose_name = _("待办(Todo)")

    @property
    def url(self):
        return f"{env.BK_SAAS_HOST}/my-todos?id={self.ticket.id}"

    def set_status(self, username, status):
        if self.status == status:
            return

        self.status = status
        if status in [TodoStatus.DONE_SUCCESS, TodoStatus.DONE_FAILED]:
            self.done_by = username
            self.done_at = timezone.now()

        self.save()

    def set_success(self, username, action):
        self.set_status(username, TodoStatus.DONE_SUCCESS)
        TodoHistory.objects.create(creator=username, todo=self, action=action)

    def set_terminated(self, username, action):
        self.set_status(username, TodoStatus.DONE_FAILED)
        self.flow.update_status(TicketFlowStatus.TERMINATED)
        TodoHistory.objects.create(creator=username, todo=self, action=action)


class TodoHistory(AuditedModel):
    """
    待办操作记录
    """

    todo = models.ForeignKey("Todo", help_text=_("关联待办"), related_name="history_of_todo", on_delete=models.CASCADE)
    action = models.CharField(_("操作"), max_length=LEN_MIDDLE, default="")

    class Meta:
        verbose_name = _("待办操作记录")
        verbose_name_plural = _("待办操作记录")
