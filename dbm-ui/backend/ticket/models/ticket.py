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
from collections import defaultdict
from typing import Any, Dict, List, Union

from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from backend import env
from backend.bk_web.constants import LEN_L_LONG, LEN_LONG, LEN_NORMAL, LEN_SHORT
from backend.bk_web.models import AuditedModel
from backend.configuration.constants import PLAT_BIZ_ID, DBType, SystemSettingsEnum
from backend.configuration.models import SystemSettings
from backend.db_monitor.exceptions import AutofixException
from backend.ticket.constants import (
    EXCLUSIVE_TICKET_EXCEL_PATH,
    TICKET_RUNNING_STATUS_SET,
    FlowErrCode,
    FlowRetryType,
    FlowType,
    TicketFlowStatus,
    TicketStatus,
    TicketType,
    TodoStatus,
)
from backend.utils.excel import ExcelHandler
from backend.utils.time import calculate_cost_time

logger = logging.getLogger("root")


class Flow(models.Model):
    """
    单据流程
    """

    create_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    update_at = models.DateTimeField(_("更新时间"), auto_now=True)
    ticket = models.ForeignKey("Ticket", help_text=_("关联工单"), related_name="flows", on_delete=models.CASCADE)
    flow_type = models.CharField(help_text=_("流程类型"), max_length=LEN_SHORT, choices=FlowType.get_choices())
    flow_alias = models.CharField(help_text=_("流程别名"), max_length=LEN_LONG, null=True, blank=True)
    # 若 flow_type 为 itsm，则 flow_obj_id 为 ITSM 单据号；若为 job，则对应 job_id；内置流程为 root_id；可扩展
    flow_obj_id = models.CharField(_("单据流程对象ID"), max_length=LEN_NORMAL, blank=True, db_index=True)
    details = models.JSONField(_("单据流程详情"), default=dict)
    status = models.CharField(
        _("单据流程状态"),
        choices=TicketFlowStatus.get_choices(),
        max_length=LEN_SHORT,
        default=TicketFlowStatus.PENDING,
    )
    err_msg = models.TextField(_("错误信息"), null=True, blank=True)
    err_code = models.FloatField(_("错误代码"), null=True, blank=True)
    retry_type = models.CharField(
        _("重试类型(专用于inner_flow)"), max_length=LEN_SHORT, choices=FlowRetryType.get_choices(), blank=True, null=True
    )
    context = models.JSONField(_("流程上下文(用于扩展字段)"), default=dict)

    class Meta:
        verbose_name_plural = verbose_name = _("单据流程(Flow)")
        indexes = [models.Index(fields=["err_code"])]

    def update_details(self, **kwargs):
        self.details.update(kwargs)
        self.save(update_fields=["details", "update_at"])
        return kwargs

    def update_status(self, status: TicketFlowStatus):
        if self.status != status:
            self.status = status
            self.save(update_fields=["status", "update_at"])
        return status


class Ticket(AuditedModel):
    """
    单据
    """

    bk_biz_id = models.IntegerField(_("业务ID"))
    ticket_type = models.CharField(
        _("单据类型"),
        choices=TicketType.get_choices(),
        max_length=LEN_NORMAL,
        default=TicketType.MYSQL_SINGLE_APPLY,
    )
    group = models.CharField(_("单据分组类型"), choices=DBType.get_choices(), max_length=LEN_NORMAL, default=DBType.MySQL)
    status = models.CharField(
        _("单据状态"),
        choices=TicketStatus.get_choices(),
        max_length=LEN_SHORT,
        default=TicketStatus.PENDING,
    )
    remark = models.CharField(_("备注"), max_length=LEN_L_LONG)
    details = models.JSONField(_("单据差异化详情"), default=dict)
    send_msg_config = models.JSONField(_("单据通知设置"), default=dict)
    is_reviewed = models.BooleanField(_("单据是否审阅过"), default=False)

    class Meta:
        verbose_name_plural = verbose_name = _("单据(Ticket)")
        ordering = ("-id",)
        indexes = [
            models.Index(fields=["creator"]),
            models.Index(fields=["bk_biz_id"]),
            models.Index(fields=["group"]),
            models.Index(fields=["status"]),
        ]

    @property
    def url(self):
        return f"{env.BK_SAAS_HOST}/ticket/{self.id}"

    @property
    def iframe_url(self):
        """iframe 单据链接，目前仅用在itsm表单"""
        return f"{env.BK_SAAS_HOST}/sub/ticket/{self.id}"

    def set_status(self, status):
        self.status = status
        self.save()

    def get_cost_time(self):
        # 计算耗时
        if self.status in [TicketStatus.PENDING, *TICKET_RUNNING_STATUS_SET]:
            return calculate_cost_time(timezone.now(), self.create_at)
        return calculate_cost_time(self.update_at, self.create_at)

    def get_terminate_reason(self):
        # 获取单据终止原因
        if self.status != TicketStatus.TERMINATED:
            return ""

        flow = self.current_flow()
        # 系统终止
        if flow.err_code == FlowErrCode.SYSTEM_TERMINATED_ERROR:
            return _("系统自动终止")
        # 用户终止，获取所有失败的todo，拿到里面的备注
        fail_todo = flow.todo_of_flow.filter(status=TodoStatus.DONE_FAILED).first()
        if not fail_todo:
            return ""
        # 格式化终止文案
        remark = fail_todo.context.get("remark", "")
        reason = _("{}已处理（人工终止，备注: {}）").format(fail_todo.done_by, remark)
        return reason

    def get_current_operators(self):
        # 获取当前流程处理人和协助人
        running_todo = self.todo_of_ticket.filter(status=TodoStatus.TODO).first()
        if not running_todo:
            return []
        return {"operators": running_todo.operators, "helpers": running_todo.helpers}

    def update_details(self, **kwargs):
        self.details.update(kwargs)
        self.save(update_fields=["details", "update_at"])

    def update_flow_details(self, **kwargs):
        self.current_flow().update_details(**kwargs)

    def current_flow(self) -> Flow:
        """
        当前的流程
         1. 取 TicketFlow 中最后一个 flow_obj_id 非空的流程
         2. 若 TicketFlow 中都流程都为空，则代表整个单据未开始，取第一个流程
        """
        if Flow.objects.filter(ticket=self).exclude(status=TicketFlowStatus.PENDING).exists():
            return Flow.objects.filter(ticket=self).exclude(status=TicketFlowStatus.PENDING).last()
        # 初始化时，当前节点和下一个节点为同一个
        return self.next_flow()

    def next_flow(self) -> Flow:
        """
        下一个流程，即 TicketFlow 中第一个为PENDING的流程
        """
        next_flows = Flow.objects.filter(ticket=self, status=TicketFlowStatus.PENDING)

        # 支持跳过人工审批和确认环节
        if env.ITSM_FLOW_SKIP:
            next_flows = next_flows.exclude(flow_type__in=[FlowType.BK_ITSM, FlowType.PAUSE])

        return next_flows.first()

    @classmethod
    def create_ticket(
        cls,
        ticket_type: TicketType,
        creator: str,
        bk_biz_id: int,
        remark: str,
        details: Dict[str, Any],
        auto_execute: bool = True,
        send_msg_config: dict = None,
    ) -> "Ticket":
        """
        自动创建单据
        :param ticket_type: 单据类型
        :param creator: 创建者
        :param bk_biz_id: 业务ID
        :param remark: 备注
        :param details: 单据参数details
        :param auto_execute: 是否自动初始化执行单据
        :param send_msg_config: 消息发送类配置
        """

        from backend.ticket.builders import BuilderFactory

        with transaction.atomic():
            send_msg_config = send_msg_config or {}
            ticket = Ticket.objects.create(
                group=BuilderFactory.get_builder_cls(ticket_type).group,
                creator=creator,
                updater=creator,
                bk_biz_id=bk_biz_id,
                ticket_type=ticket_type,
                remark=remark,
                details=details,
                send_msg_config=send_msg_config,
            )
            logger.info(_("正在自动创建单据，单据详情: {}").format(ticket.__dict__))
            builder = BuilderFactory.create_builder(ticket)
            builder.patch_ticket_detail()
            builder.init_ticket_flows()

        if auto_execute:
            # 开始单据流程
            from backend.ticket.flow_manager.manager import TicketFlowManager

            logger.info(_("单据{}正在初始化流程").format(ticket.id))
            TicketFlowManager(ticket=ticket).run_next_flow()

        return ticket

    @classmethod
    def create_ticket_from_bk_monitor(cls, callback_data):
        """
        从蓝鲸监控告警事件发起创建单据
        """
        from backend.ticket.builders import BuilderFactory

        for ticket_type in callback_data["ticket_types"]:
            alarm_transform_serializer = BuilderFactory.get_builder_cls(ticket_type).alarm_transform_serializer
            if alarm_transform_serializer is None:
                raise AutofixException(_("不支持该类型的单据"))
            ticket_details = alarm_transform_serializer().to_internal_value(callback_data)
            cls.create_ticket(
                ticket_type=ticket_type,
                creator=callback_data["creator"],
                bk_biz_id=callback_data["callback_message"]["event"]["dimensions"]["appid"],
                remark=_("发起故障自愈，告警事件 ID：").format(callback_data["callback_message"]["event"]["id"]),
                details=ticket_details,
            )


class TicketFlowsConfig(AuditedModel):
    """
    单据流程配置，暂时只可配置单据审批、人工确认
    """

    bk_biz_id = models.IntegerField(_("业务ID"), default=0)
    cluster_ids = models.JSONField(_("集群ID列表"), default=list)
    group = models.CharField(_("单据分组类型"), choices=DBType.get_choices(), max_length=LEN_NORMAL)
    ticket_type = models.CharField(_("单据类型"), choices=TicketType.get_choices(), max_length=128)
    editable = models.BooleanField(_("是否支持用户配置"), default=True)
    configs = models.JSONField(_("单据配置 eg: {'need_itsm': false, 'need_manual_confirm': false}"), default=dict)

    class Meta:
        verbose_name_plural = verbose_name = _("单据流程配置(TicketFlowsConfig)")
        indexes = [models.Index(fields=["group"]), models.Index(fields=["bk_biz_id"])]

    @classmethod
    def get_cluster_configs(cls, ticket_type, bk_biz_id, cluster_ids):
        """获取集群生效的流程配置"""
        # 流程优先级：集群维度 > 业务维度 > 平台维度
        # 全局配置
        global_cfg = cls.objects.get(bk_biz_id=PLAT_BIZ_ID, ticket_type=ticket_type)
        # 业务配置和集群配置
        biz_configs = cls.objects.filter(bk_biz_id=bk_biz_id, ticket_type=ticket_type)
        biz_cfg = biz_configs.filter(cluster_ids=[]).first() or global_cfg
        cluster_cfg = biz_configs.exclude(cluster_ids=[]).first() or biz_cfg

        # 单据不涉及集群，则返回业务/平台配置
        if not cluster_ids:
            return [biz_cfg]

        # 业务或集群配置最多共存一个
        cluster_configs = [
            cluster_cfg if cluster_cfg and cluster_id in cluster_cfg.cluster_ids else biz_cfg
            for cluster_id in cluster_ids
        ]
        return cluster_configs

    @classmethod
    def get_config(cls, ticket_type):
        """获取平台配置"""
        global_cfg = cls.objects.get(bk_biz_id=PLAT_BIZ_ID, ticket_type=ticket_type)
        return global_cfg


class ClusterOperateRecordManager(models.Manager):
    def filter_actives(self, cluster_id, *args, **kwargs):
        """获得集群正在运行的单据记录"""
        return self.filter(cluster_id=cluster_id, ticket__status=TicketStatus.RUNNING, *args, **kwargs)

    def filter_inner_actives(self, cluster_id, *args, **kwargs):
        """获取集群正在 运行/失败 的inner flow的单据记录。此时认为集群会在互斥阶段"""
        # 排除特定的单据，如自身单据重试排除自身
        exclude_ticket_ids = kwargs.pop("exclude_ticket_ids", [])
        return (
            self.select_related("ticket")
            .filter(
                cluster_id=cluster_id,
                flow__flow_type=FlowType.INNER_FLOW,
                flow__status__in=[TicketFlowStatus.RUNNING, TicketFlowStatus.FAILED],
                *args,
                **kwargs,
            )
            .exclude(flow__ticket_id__in=exclude_ticket_ids)
        )

    def get_cluster_operations(self, cluster_id, **kwargs):
        """集群上的正在运行的操作列表"""
        return [r.summary for r in self.filter_actives(cluster_id, **kwargs)]

    def has_exclusive_operations(self, ticket_type, cluster_id, **kwargs):
        """判断当前单据类型与集群正在进行中的单据是否互斥"""
        active_records = self.filter_inner_actives(cluster_id, **kwargs)
        exclusive_ticket_map = self.get_exclusive_ticket_map()
        exclusive_infos = []
        for record in active_records:
            active_ticket_type = record.ticket.ticket_type
            # 记录互斥信息。不存在互斥表默认为互斥
            if exclusive_ticket_map.get(ticket_type, {}).get(active_ticket_type, True):
                exclusive_infos.append({"exclusive_ticket": record.ticket, "root_id": record.flow.flow_obj_id})
        return exclusive_infos

    @staticmethod
    def get_exclusive_ticket_map(force=False):
        """获取单据互斥状态表, force为True表示强制刷新"""
        exclusive_map = SystemSettings.get_setting_value(key=SystemSettingsEnum.EXCLUSIVE_TICKET_MAP, default={})
        if exclusive_map and not force:
            return exclusive_map

        exclusive_map = defaultdict(dict)
        exclusive_matrix = ExcelHandler.paser_matrix(EXCLUSIVE_TICKET_EXCEL_PATH)
        for row_label, inner_dict in exclusive_matrix.items():
            for col_label, value in inner_dict.items():
                row_key, col_key = TicketType.get_choice_value(row_label), TicketType.get_choice_value(col_label)
                exclusive_map[row_key][col_key] = value == "N"

        SystemSettings.insert_setting_value(
            key=SystemSettingsEnum.EXCLUSIVE_TICKET_MAP, value=exclusive_map, value_type="dict"
        )
        return exclusive_map


class ClusterOperateRecord(AuditedModel):
    """
    集群操作记录
    """

    cluster_id = models.IntegerField(_("集群ID"))
    flow = models.ForeignKey("Flow", help_text=_("关联流程任务"), on_delete=models.CASCADE)
    ticket = models.ForeignKey("Ticket", help_text=_("关联工单"), on_delete=models.CASCADE)

    objects = ClusterOperateRecordManager()

    class Meta:
        # cluster_id, flow和ticket组成唯一性校验
        unique_together = (("cluster_id", "flow", "ticket"),)

    @property
    def summary(self):
        return {
            "operator": self.creator,
            "cluster_id": self.cluster_id,
            "flow_id": self.flow.id,
            "ticket_id": self.ticket.id,
            "ticket_type": self.ticket.ticket_type,
            "title": TicketType.get_choice_label(self.ticket.ticket_type),
            "status": self.ticket.status,
        }

    @classmethod
    def get_cluster_records_map(cls, cluster_ids: List[int]):
        """获取集群与操作记录之间的映射关系"""
        records = cls.objects.select_related("ticket", "flow").filter(
            cluster_id__in=cluster_ids, ticket__status__in=TICKET_RUNNING_STATUS_SET
        )
        cluster_operate_records_map: Dict[int, List] = defaultdict(list)
        for record in records:
            cluster_operate_records_map[record.cluster_id].append(record.summary)
        return cluster_operate_records_map


class InstanceOperateRecordManager(models.Manager):
    REBOOT_TICKET_TYPES = {
        TicketType.ES_REBOOT,
        TicketType.KAFKA_REBOOT,
        TicketType.HDFS_REBOOT,
        TicketType.INFLUXDB_REBOOT,
        TicketType.PULSAR_REBOOT,
        TicketType.RIAK_CLUSTER_REBOOT,
        TicketType.DORIS_REBOOT,
    }

    def filter_actives(self, instance_id, **kwargs):
        return self.filter(
            instance_id=instance_id,
            ticket__status=TicketStatus.RUNNING,
            **kwargs,
        )

    def get_locking_operations(self, instance_id, **kwargs):
        """实例上的锁定操列表"""
        return [r.summary for r in self.filter_actives(instance_id, **kwargs)]

    def has_locked_operations(self, instance_id, **kwargs):
        """是否有锁定实例的操作在执行"""
        return self.filter_actives(instance_id, **kwargs).exists()


class InstanceOperateRecord(AuditedModel):
    """
    实例操作记录
    TODO: 是否考虑定期清理记录
    """

    # 如果是大数据，可以将storage_instance的id作为instance_id存入，如果是其他集群，则将bk_host_id:port存入。
    # 原则上将bk_host_id:port存入是最好的，目前只是兼容大数据的设计
    instance_id = models.CharField(_("实例ID"), max_length=128)

    flow = models.ForeignKey("Flow", help_text=_("关联流程任务"), on_delete=models.CASCADE)
    ticket = models.ForeignKey("Ticket", help_text=_("关联工单"), on_delete=models.CASCADE)

    objects = InstanceOperateRecordManager()

    @property
    def summary(self):
        return {
            "operator": self.creator,
            "instance_id": self.instance_id,
            "flow_id": self.flow.id,
            "ticket_id": self.ticket.id,
            "ticket_type": self.ticket.ticket_type,
            "title": self.ticket.get_ticket_type_display(),
            "status": self.ticket.status,
        }

    @classmethod
    def get_instance_records_map(cls, instance_ids: List[Union[int, str]]):
        """获取实例与操作记录之间的映射关系??????"""
        records = InstanceOperateRecord.objects.select_related("ticket").filter(
            instance_id__in=instance_ids, ticket__status__in=TICKET_RUNNING_STATUS_SET
        )
        instance_operator_record_map: Dict[int, List] = defaultdict(list)
        for record in records:
            instance_operator_record_map[record.instance_id].append(record.summary)
        return instance_operator_record_map
