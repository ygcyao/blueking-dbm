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
import datetime
import json
import logging
import os
from collections import defaultdict
from typing import Any, Dict, List

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from backend import env
from backend.bk_web.constants import LEN_MIDDLE, LEN_NORMAL, LEN_SHORT
from backend.bk_web.models import AuditedModel
from backend.components import BKMonitorV3Api
from backend.configuration.constants import PLAT_BIZ_ID, DBType, SystemSettingsEnum
from backend.configuration.models import SystemSettings
from backend.db_meta.enums import ClusterType
from backend.db_meta.models import AppMonitorTopo, DBModule
from backend.db_monitor.constants import (
    APP_PRIORITY,
    BK_MONITOR_DISPATCH_RULE_MIXIN,
    BK_MONITOR_SAVE_DISPATCH_GROUP_TEMPLATE,
    BK_MONITOR_SAVE_USER_GROUP_TEMPLATE,
    DEFAULT_ALERT_NOTICE,
    PLAT_PRIORITY,
    TARGET_LEVEL_TO_PRIORITY,
    TPLS_ALARM_DIR,
    AlertSourceEnum,
    DutyRuleCategory,
    PolicyStatus,
    TargetLevel,
    TargetPriority,
)
from backend.db_monitor.exceptions import (
    BkMonitorDeleteAlarmException,
    BkMonitorSaveAlarmException,
    BuiltInNotAllowDeleteException,
    DutyRuleSaveException,
)
from backend.db_monitor.tasks import delete_monitor_duty_rule, update_app_policy, update_db_notice_group
from backend.db_monitor.utils import (
    bkm_delete_alarm_strategy,
    bkm_save_alarm_strategy,
    get_dbm_autofix_action_id,
    render_promql_sql,
)
from backend.db_services.cmdb.biz import list_cc_obj_user
from backend.exceptions import ApiError

__all__ = ["NoticeGroup", "AlertRule", "RuleTemplate", "DispatchGroup", "MonitorPolicy", "DutyRule"]

logger = logging.getLogger("root")


class NoticeGroup(AuditedModel):
    """告警通知组：一期粒度仅支持到业务级，可开关是否同步DBA人员数据"""

    bk_biz_id = models.IntegerField(help_text=_("业务ID, 0代表全业务"), default=PLAT_BIZ_ID)
    name = models.CharField(_("告警通知组名称"), max_length=LEN_MIDDLE, default="")
    monitor_group_id = models.BigIntegerField(help_text=_("监控通知组ID"), default=0)
    monitor_duty_rule_id = models.IntegerField(verbose_name=_("监控轮值规则 ID"), default=0)
    db_type = models.CharField(_("数据库类型"), choices=DBType.get_choices(), max_length=LEN_SHORT, default="")
    receivers = models.JSONField(_("告警接收人员/组列表"), default=dict)
    details = models.JSONField(verbose_name=_("通知方式详情"), default=dict)
    is_built_in = models.BooleanField(verbose_name=_("是否内置"), default=False)
    sync_at = models.DateTimeField(_("最近一次的同步时间"), null=True)
    dba_sync = models.BooleanField(help_text=_("自动同步DBA人员配置"), default=True)

    class Meta:
        verbose_name_plural = verbose_name = _("告警通知组(NoticeGroup)")
        unique_together = ("bk_biz_id", "name")

    @classmethod
    def get_monitor_groups(cls, db_type=None, group_ids=None, **kwargs):
        """查询监控告警组id"""
        qs = cls.objects.all()

        if db_type:
            qs = qs.filter(db_type=db_type)

        if group_ids is not None:
            qs = qs.filter(id__in=group_ids)

        # is_built_in/bk_biz_id等
        if kwargs:
            qs = qs.filter(**kwargs)

        # 根据 group_ids 排序 返回 monitor_group_id 列表
        id_monitor_group_id_map = {
            item["id"]: item["monitor_group_id"] for item in qs.values("id", "monitor_group_id")
        }
        return [id_monitor_group_id_map[group_id] for group_id in group_ids]

    @classmethod
    def get_groups(cls, bk_biz_id, id_name="monitor_group_id") -> dict:
        """业务内置"""
        return dict(cls.objects.filter(bk_biz_id=bk_biz_id, is_built_in=True).values_list("db_type", id_name))

    def transfer_receivers(self):
        """转换接收人，主要是把 cc 角色用户打散为具体用户"""
        receivers = []
        obj_id_members = None
        for receiver in self.receivers:
            # 针对 cc 角色，需要转成真实业务的人员
            if receiver.get("type") == "group":
                if obj_id_members is None:
                    biz_obj_user = list_cc_obj_user(self.bk_biz_id)
                    obj_id_members = {obj_user["id"]: obj_user["members"] for obj_user in biz_obj_user}
                members = obj_id_members.get(receiver["id"]) or []
                for member in members:
                    receivers.append({"id": member, "type": "user"})
            else:
                receivers.append(receiver)
        return receivers

    def save_monitor_group(self) -> int:
        # 深拷贝保存用户组的模板
        save_monitor_group_params = copy.deepcopy(BK_MONITOR_SAVE_USER_GROUP_TEMPLATE)
        # 更新差异字段
        bk_monitor_group_name = f"{self.name}_{self.bk_biz_id}"
        save_monitor_group_params.update(
            {
                "name": bk_monitor_group_name,
                "alert_notice": self.details.get("alert_notice") or DEFAULT_ALERT_NOTICE,
                "bk_biz_id": env.DBA_APP_BK_BIZ_ID,
            }
        )
        if self.is_built_in:
            # 内置告警组
            # 创建/更新一条轮值规则
            rule_name = f"{self.name}_{self.bk_biz_id}"
            save_duty_rule_params = {
                "name": rule_name,
                "bk_biz_id": env.DBA_APP_BK_BIZ_ID,
                "effective_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": "",
                "labels": [self.db_type],
                "enabled": True,
                "category": DutyRuleCategory.REGULAR.value,
                "duty_arranges": [
                    {
                        "duty_time": [{"work_type": "daily", "work_time": ["00:00--23:59"]}],
                        "duty_users": [self.receivers],
                    }
                ],
            }
            if self.monitor_duty_rule_id:
                save_duty_rule_params["id"] = self.monitor_duty_rule_id
            else:
                rules = BKMonitorV3Api.search_duty_rules({"bk_biz_ids": [env.DBA_APP_BK_BIZ_ID], "name": rule_name})
                for rule in rules:
                    if rule["name"].lower() == rule_name.lower():
                        save_duty_rule_params["id"] = rule["id"]
                        self.monitor_duty_rule_id = rule["id"]

            resp = BKMonitorV3Api.save_duty_rule(save_duty_rule_params, use_admin=True, raw=True)
            if resp.get("result"):
                self.monitor_duty_rule_id = resp["data"]["id"]
                duty_rules = DutyRule.get_biz_db_duty_rules(self.bk_biz_id, self.db_type)
                monitor_duty_rule_ids = [rule.monitor_duty_rule_id for rule in duty_rules]
                save_monitor_group_params["need_duty"] = True
                save_monitor_group_params["duty_rules"] = list(monitor_duty_rule_ids) + [self.monitor_duty_rule_id]
            else:
                if resp.get("code") == BKMonitorV3Api.ErrorCode.DUTY_RULE_NAME_ALREADY_EXISTS:
                    logger.warning(f"duty_rule_name_already_exists,resp:{resp}")
                else:
                    logger.error(f"request monitor api error: {ApiError}")
                save_monitor_group_params["duty_arranges"][0]["users"] = self.receivers

        else:
            receivers = self.transfer_receivers()
            save_monitor_group_params["duty_arranges"][0]["users"] = receivers

        if self.monitor_group_id:
            save_monitor_group_params["id"] = self.monitor_group_id

        # 调用监控接口写入

        resp = BKMonitorV3Api.save_user_group(
            save_monitor_group_params,
            use_admin=True,
            raw=True,
        )
        if resp.get("result"):
            self.sync_at = datetime.datetime.now(timezone.utc)
            return resp["data"]["id"]

        if resp.get("code") == BKMonitorV3Api.ErrorCode.MONITOR_GROUP_NAME_ALREADY_EXISTS:
            bk_monitor_groups = BKMonitorV3Api.search_user_groups(
                {"bk_biz_ids": [env.DBA_APP_BK_BIZ_ID], "name": bk_monitor_group_name}
            )
            for group in bk_monitor_groups:
                if group["name"].lower() == bk_monitor_group_name.lower():
                    save_monitor_group_params["id"] = group["id"]
            resp = BKMonitorV3Api.save_user_group(save_monitor_group_params)
            self.sync_at = datetime.datetime.now(timezone.utc)
            return resp["id"]

        else:
            raise ApiError(f"save_user_group({bk_monitor_group_name}) error, resp:{resp}")

    def save(self, *args, **kwargs):
        """
        保存告警组
        """
        self.monitor_group_id = self.save_monitor_group()
        if self.is_built_in:
            # 更新业务策略绑定的告警组
            update_app_policy.delay(self.bk_biz_id, self.id, self.db_type)
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        if self.is_built_in:
            raise BuiltInNotAllowDeleteException
        BKMonitorV3Api.delete_user_groups({"ids": [self.monitor_group_id], "bk_biz_ids": [env.DBA_APP_BK_BIZ_ID]})
        super().delete()


class DutyRule(AuditedModel):
    """
    轮值规则，仅为平台设置，启用后默认应用到所有内置告警组
    duty_arranges:
    交替轮值（category=handoff）
    [
        {
            "duty_number": 2,
            "duty_day": 1,
            "members": ["admin"],
            "work_type": "weekly",
            "work_days": [6, 7],
            "work_times": ["00:00--11:59", "12:00--23:59"]
        }
    ]
    常规轮值/自定义（category=regular）
    [
        {
            "date": "2023-10-01",
            "work_times": ["00:00--11:59", "12:00--23:59"],
            "members": ["admin"]
        },
        {
            "date": "2023-10-02",
            "work_times": ["08:00--18:00"],
            "members": ["admin"]
        },
        {
            "date": "2023-10-03",
            "work_times": ["00:00--11:59", "12:00--23:59"],
            "members": ["admin"]
        }
    ]
    """

    name = models.CharField(verbose_name=_("轮值规则名称"), max_length=LEN_MIDDLE)
    monitor_duty_rule_id = models.IntegerField(verbose_name=_("监控轮值规则 ID"), default=0)
    priority = models.PositiveIntegerField(verbose_name=_("优先级"))
    is_enabled = models.BooleanField(verbose_name=_("是否启用"), default=True)
    effective_time = models.DateTimeField(verbose_name=_("生效时间"))
    end_time = models.DateTimeField(verbose_name=_("截止时间"), blank=True, null=True)
    category = models.CharField(verbose_name=_("轮值类型"), choices=DutyRuleCategory.get_choices(), max_length=LEN_SHORT)
    db_type = models.CharField(_("数据库类型"), choices=DBType.get_choices(), max_length=LEN_SHORT)
    duty_arranges = models.JSONField(_("轮值人员设置"))
    biz_config = models.JSONField(_("业务设置(包含业务include/排除业务exclude)"), default=dict)

    def save(self, *args, **kwargs):
        """
        保存轮值
        """
        # 0. (前置校验)不允许同时存在包含业务和排除业务两个设置
        if self.biz_config.get("include") and self.biz_config.get("exclude"):
            raise DutyRuleSaveException(_("不允许通知存在包含业务和排除业务配置"))
        # 1. 新建监控轮值
        params = {
            "name": f"{self.db_type}_{self.name}",
            "bk_biz_id": env.DBA_APP_BK_BIZ_ID,
            "effective_time": self.effective_time
            if isinstance(self.effective_time, str)
            else self.effective_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": self.end_time.strftime("%Y-%m-%d %H:%M:%S") if self.end_time else "",
            "labels": [self.db_type],
            "enabled": self.is_enabled,
            "category": self.category,
        }
        if self.category == DutyRuleCategory.REGULAR.value:
            params["duty_arranges"] = [
                {
                    "duty_time": [
                        {
                            "work_type": "monthly",
                            "work_days": [int(arrange["date"].split("-")[-1])],
                            "work_time": arrange["work_times"],
                        }
                    ],
                    "duty_users": [[{"id": member, "type": "user"} for member in arrange["members"]]],
                }
                for arrange in self.duty_arranges
            ]
        else:
            try:
                group_number = self.duty_arranges[0]["duty_number"]
            except (IndexError, ValueError):
                group_number = 1
            params.update(
                **{
                    "duty_arranges": [
                        {
                            "duty_time": [
                                {
                                    "work_type": arrange["work_type"],
                                    "work_days": arrange["work_days"],
                                    "work_time": arrange["work_times"],
                                    "period_settings": {
                                        "window_unit": "day",
                                        "duration": self.duty_arranges[0]["duty_day"],
                                    },
                                }
                            ],
                            "duty_users": [[{"id": member, "type": "user"} for member in arrange["members"]]],
                        }
                        for arrange in self.duty_arranges
                    ],
                    "group_type": "auto",
                    "group_number": group_number,
                }
            )
        #  2. 判断是否存量的轮值规则，如果是，则走更新流程
        is_old_rule = bool(self.monitor_duty_rule_id)
        if bool(self.monitor_duty_rule_id):
            params["id"] = self.monitor_duty_rule_id
        resp = BKMonitorV3Api.save_duty_rule(params)
        self.monitor_duty_rule_id = resp["id"]
        # 3. 判断是否需要变更用户组
        # 3.1 非老规则（即新建的规则）
        need_update_user_group = not is_old_rule
        # 3.2 调整了优先级的规则，或者调整了业务配置
        if self.pk:
            old_rule = DutyRule.objects.get(pk=self.pk)
            if old_rule.priority != self.priority or old_rule.biz_config != self.biz_config:
                need_update_user_group = True
        # 4. 保存本地轮值规则
        super().save(*args, **kwargs)
        # 5. 变更告警组-异步执行
        if need_update_user_group:
            update_db_notice_group.delay(self.db_type)

    def delete(self, using=None, keep_parents=False):
        """删除轮值"""
        super().delete()
        delete_monitor_duty_rule.delay(self.db_type, self.monitor_duty_rule_id)

    @classmethod
    def priority_distinct(cls) -> list:
        return list(cls.objects.values_list("priority", flat=True).distinct().order_by("-priority"))

    @classmethod
    def get_biz_db_duty_rules(cls, bk_biz_id: int, db_type: str):
        """获取指定业务DB组件的轮值策略"""
        duty_rules = DutyRule.objects.filter(db_type=db_type).exclude(monitor_duty_rule_id=0).order_by("-priority")
        active_biz_duty_rules: list = []

        for rule in duty_rules:
            # 如果业务不在包含名单，或者业务在排除名单，则本策略不属于该业务下
            if rule.biz_config:
                include, exclude = rule.biz_config.get("include"), rule.biz_config.get("exclude")
                if (include and bk_biz_id not in include) or (exclude and bk_biz_id in exclude):
                    continue
            # 添加该业务下的轮值策略
            active_biz_duty_rules.append(rule)

        return active_biz_duty_rules

    class Meta:
        verbose_name_plural = verbose_name = _("轮值规则(DutyRule)")


class RuleTemplate(AuditedModel):
    """告警策略模板：just for export"""

    bk_biz_id = models.IntegerField(help_text=_("业务ID, 0代表全业务"), default=PLAT_BIZ_ID)
    monitor_strategy_id = models.IntegerField(help_text=_("监控策略ID"), default=0)

    name = models.CharField(verbose_name=_("策略名称监控侧要求唯一"), max_length=LEN_MIDDLE, unique=True)
    db_type = models.CharField(
        _("DB类型"), choices=DBType.get_choices(), max_length=LEN_NORMAL, default=DBType.MySQL.value
    )

    details = models.JSONField(verbose_name=_("模板详情"), default=dict)
    is_enabled = models.BooleanField(_("是否启用"), default=True)

    class Meta:
        verbose_name = _("告警策略模板")


class AlertRule(AuditedModel):
    """TODO: 告警策略实例：deprecated"""

    bk_biz_id = models.IntegerField(help_text=_("业务ID, 0代表全业务"), default=PLAT_BIZ_ID)

    template_id = models.IntegerField(help_text=_("监控模板ID"), default=0)
    monitor_strategy_id = models.IntegerField(help_text=_("监控策略ID"), default=0)

    name = models.CharField(verbose_name=_("策略名称"), max_length=LEN_MIDDLE, default="")
    db_type = models.CharField(
        _("DB类型"), choices=DBType.get_choices(), max_length=LEN_NORMAL, default=DBType.MySQL.value
    )

    details = models.JSONField(verbose_name=_("实例详情"), default=dict)
    is_enabled = models.BooleanField(_("是否启用"), default=True)

    @classmethod
    def clear(cls, ids=None):
        """清理所有平台告警策略"""

        ids = list(cls.objects.all().values_list("monitor_policy_id", flat=True)) if not ids else ids.split(",")
        params = {"bk_biz_id": env.DBA_APP_BK_BIZ_ID, "ids": ids}
        response = BKMonitorV3Api.delete_alarm_strategy_v3(params, use_admin=True, raw=True)
        if not response.get("result"):
            logger.error("bkm_delete_alarm_strategy failed: params: %s\n response: %s", params, response)
            raise BkMonitorDeleteAlarmException(message=response.get("message"))

        cls.objects.all().delete()

    class Meta:
        verbose_name = _("告警策略实例")


class DispatchGroup(AuditedModel):
    """分派策略组"""

    bk_biz_id = models.IntegerField(verbose_name=_("业务ID, 0代表全业务"), default=PLAT_BIZ_ID, unique=True)
    monitor_dispatch_id = models.IntegerField(verbose_name=_("蓝鲸监控分派策略组ID"), default=0)
    # name = models.CharField(verbose_name=_("策略名称，全局唯一"), max_length=LEN_MIDDLE)
    # priority = models.PositiveIntegerField(verbose_name=_("监控策略优先级，跟随targets调整"))
    details = models.JSONField(verbose_name=_("策略模板详情"), default=dict)
    rules = models.JSONField(verbose_name=_("规则列表"), default=list)
    # is_synced = models.BooleanField(verbose_name=_("是否已同步到监控"), default=False)
    sync_at = models.DateTimeField(_("最近一次的同步时间"), null=True)

    class Meta:
        verbose_name = _("分派策略组")

    @classmethod
    def save_dispatch_group(cls, params):
        return BKMonitorV3Api.save_rule_group(params)

    @classmethod
    def get_rules_by_dbtype(cls, db_type, bk_biz_id) -> List[Dict[str, Any]]:
        """根据db类型生成规则"""
        rules = []

        user_groups = [NoticeGroup.get_groups(bk_biz_id).get(db_type)]
        # 特殊策略需要独立分派
        dispatch_policies = MonitorPolicy.get_dispatch_policies()
        if db_type in [DBType.MySQL, DBType.TenDBCluster, DBType.Redis, DBType.Sqlserver]:
            conditions = [
                {"field": "alert.strategy_id", "method": "eq", "value": dispatch_policies, "condition": "and"},
                {
                    "field": "cluster_type",
                    "method": "eq",
                    "value": ClusterType.db_type_to_cluster_types(db_type),
                    "condition": "and",
                },
            ]
            if bk_biz_id != PLAT_BIZ_ID:
                conditions.append({"field": "appid", "method": "eq", "value": [str(bk_biz_id)], "condition": "and"})
            rules.append(
                {
                    "user_groups": user_groups,
                    "conditions": conditions,
                    **BK_MONITOR_DISPATCH_RULE_MIXIN,
                }
            )

        # 仅分派平台策略，排除掉需要特殊分派的策略
        policies = list(set(MonitorPolicy.get_policies(db_type)) - set(dispatch_policies))
        if policies:
            conditions = [{"field": "alert.strategy_id", "value": policies, "method": "eq", "condition": "and"}]

            # 业务级分派策略
            if bk_biz_id != PLAT_BIZ_ID:
                conditions.append({"field": "appid", "value": [str(bk_biz_id)], "method": "eq", "condition": "and"})

            rules.append(
                {
                    "user_groups": user_groups,
                    "conditions": conditions,
                    **BK_MONITOR_DISPATCH_RULE_MIXIN,
                }
            )

        return rules

    @classmethod
    def get_rules(cls, bk_biz_id=PLAT_BIZ_ID):
        rules = []

        notify_groups = NoticeGroup.objects.filter(is_built_in=True, bk_biz_id=bk_biz_id)
        for db_type in notify_groups.values_list("db_type", flat=True):
            db_type_rules = cls.get_rules_by_dbtype(db_type, bk_biz_id)

            if not db_type_rules:
                continue

            rules.extend(db_type_rules)

        return rules

    def save(self, *args, **kwargs):
        """
        保存分派规则组
        """

        data = copy.deepcopy(BK_MONITOR_SAVE_DISPATCH_GROUP_TEMPLATE)
        data.update(
            {
                "name": _("DBM平台规则_勿动_{}").format(self.bk_biz_id),
                "bk_biz_id": env.DBA_APP_BK_BIZ_ID,
                # 请求参数格式错误：(priority) 当前业务下已经存在优先级别为(100)的分派规则组
                # 优先级必能重复，故叠加业务id作为优先级调整
                "priority": PLAT_PRIORITY if self.bk_biz_id == PLAT_BIZ_ID else APP_PRIORITY + self.bk_biz_id,
                "rules": self.rules,
            }
        )

        if self.monitor_dispatch_id:
            data["id"] = self.monitor_dispatch_id
            data["assign_group_id"] = self.monitor_dispatch_id

            # 复用旧的rule_id
            for index, rule_id in enumerate(self.details.get("rules", [])[: len(self.rules)]):
                data["rules"][index]["id"] = rule_id

        # 调用监控接口写入
        resp = self.save_dispatch_group(data)
        self.monitor_dispatch_id = resp.get("assign_group_id", 0)

        self.details = resp
        self.sync_at = datetime.datetime.now(timezone.utc)

        super().save(*args, **kwargs)


class MonitorPolicy(AuditedModel):
    """监控策略"""

    KEEPED_FIELDS = [*AuditedModel.AUDITED_FIELDS, "id", "is_enabled", "monitor_policy_id", "policy_status"]

    parent_id = models.IntegerField(verbose_name=_("父级策略ID，0代表父级"), default=0)
    parent_details = models.JSONField(verbose_name=_("父级策略模板详情，可用于还原"), default=dict)

    name = models.CharField(verbose_name=_("策略名称，全局唯一"), max_length=LEN_MIDDLE, unique=True)
    bk_biz_id = models.IntegerField(verbose_name=_("业务ID, 0代表全业务"), default=PLAT_BIZ_ID)

    db_type = models.CharField(
        _("DB类型"), choices=DBType.get_choices(), max_length=LEN_NORMAL, default=DBType.MySQL.value
    )

    details = models.JSONField(verbose_name=_("当前策略详情，可用于patch"), default=dict)
    monitor_indicator = models.CharField(verbose_name=_("监控指标名"), max_length=LEN_MIDDLE, default="")

    # 拆解部分details中的字段到外层
    # TODO: MethodEnum: eq|neq|include|exclude|regex|nregex
    # item[*].query_configs[*].agg_condition[*]
    # {
    #     "agg_condition": [
    #         {
    #             "key": "appid",
    #             "dimension_name": "dbm_meta app id",
    #             "value": [
    #                 "2"
    #             ],
    #             "method": "eq",
    #             "condition": "and"
    #         },
    #         {
    #             "key": "db_module",
    #             "dimension_name": "dbm_meta db module",
    #             "value": [
    #                 "zookeeper"
    #             ],
    #             "method": "eq",
    #             "condition": "and"
    #         }
    #         {
    #             "key": "cluster_domain",
    #             "dimension_name": "dbm_meta cluster domain",
    #             "value": [
    #                 "spider.spidertest.db"
    #             ],
    #             "method": "eq",
    #             "condition": "and"
    #         },
    #     ]
    # }
    # [{"level": platform, "rule":{"key": "appid/db_module/cluster_domain", "value": ["aa", "bb"]}}]
    targets = models.JSONField(verbose_name=_("监控目标"), default=list)
    target_level = models.CharField(
        verbose_name=_("监控目标级别，跟随targets调整"),
        choices=TargetLevel.get_choices(),
        max_length=LEN_NORMAL,
        default=TargetLevel.APP.value,
    )
    target_priority = models.PositiveIntegerField(verbose_name=_("监控策略优先级，跟随targets调整"))
    target_keyword = models.TextField(verbose_name=_("监控目标检索冗余字段"), default="")

    # [{"key": "abc", "method": "eq", "value": ["aa", "bb"], "condition": "and", "dimension_name": "abc"}]
    custom_conditions = models.JSONField(verbose_name=_("自定义过滤列表"), default=list)

    # Type 目前仅支持 Threshold
    # level: 1（致命）、2（预警）、3(提醒)
    # item[*].algorithms[*]:
    # {
    #    "id": 6212,
    #    "type": "Threshold",
    #    "level": 1,
    #    "config": [
    #      [
    #        {
    #          "method": "gte",
    #          "threshold": 90
    #        }
    #      ]
    #    ],
    #    "unit_prefix": "%"
    # }
    # [{"level": 1, "config": [[{"method": "gte", "threshold": 90}]], "unit_prefix": "%"}]
    test_rules = models.JSONField(verbose_name=_("检测规则"), default=list)
    # NoticeSignalEnum: notice.signal -> ["recovered", "abnormal", "closed", "ack", "no_data"]
    # item[*].no_data_config.is_enabled
    notify_rules = models.JSONField(verbose_name=_("通知规则"), default=list)
    # [1,2,3]
    notify_groups = models.JSONField(verbose_name=_("通知组"), default=list)
    # .notice.options.assign_mode = ["by_rule", "only_notice"]
    # assign_mode = models.JSONField(verbose_name=_("通知模式-分派|直接通知"), default=list)

    is_enabled = models.BooleanField(verbose_name=_("是否已启用"), default=True)

    # 当 is_synced=True时，才有效
    sync_at = models.DateTimeField(_("最近一次的同步时间"), null=True)
    event_count = models.IntegerField(verbose_name=_("告警事件数量，初始值设置为-1"), default=-1)

    # 意义不大
    policy_status = models.CharField(
        verbose_name=_("策略状态"),
        choices=PolicyStatus.get_choices(),
        max_length=LEN_NORMAL,
        default=PolicyStatus.VALID.value,
    )

    monitor_policy_id = models.BigIntegerField(verbose_name=_("蓝鲸监控策略ID"), default=0)

    # 支持版本管理
    version = models.IntegerField(verbose_name=_("版本"), default=0)

    alert_source = models.CharField(
        verbose_name=_("告警数据来源"),
        max_length=LEN_SHORT,
        choices=AlertSourceEnum.get_choices(),
        default=AlertSourceEnum.TIME_SERIES,
    )

    class Meta:
        verbose_name = _("告警策略(MonitorPolicy)")

    def calc_from_targets(self):
        """根据目标计算优先级"""

        target_levels = list(map(lambda x: x["level"], self.targets))

        if TargetLevel.CUSTOM.value in target_levels:
            target_level = TargetLevel.CUSTOM.value
        elif TargetLevel.CLUSTER.value in target_levels:
            target_level = TargetLevel.CLUSTER.value
        elif TargetLevel.MODULE.value in target_levels:
            target_level = TargetLevel.MODULE.value
        elif TargetLevel.APP.value in target_levels:
            target_level = TargetLevel.APP.value
        else:
            target_level = TargetLevel.PLATFORM.value

        self.target_level = target_level
        self.target_priority = TARGET_LEVEL_TO_PRIORITY.get(target_level).value

        db_module_map = DBModule.db_module_map()
        self.target_keyword = ",".join(
            [
                db_module_map.get(int(value), value) if t["rule"]["key"] == TargetLevel.MODULE.value else value
                for t in self.targets
                for value in t["rule"]["value"]
            ]
        )

        # self.local_save()

    @staticmethod
    def patch_bk_biz_id(details):
        """策略要跟随主机所属的cc业务，默认为dba业务"""
        details["bk_biz_id"] = env.DBA_APP_BK_BIZ_ID
        return details

    def patch_target_and_metric_id(self, details, db_type):
        """监控目标/自定义事件和指标需要渲染
        metric_id: {bk_biz_id}_bkmoinitor_event_{event_data_id}
        """

        bkm_dbm_report: dict = SystemSettings.get_setting_value(key=SystemSettingsEnum.BKM_DBM_REPORT.value)

        items = details["items"]
        # 事件类告警，无需设置告警目标，否则要求上报的数据必须携带服务实例id（告警目标匹配依据）
        for item in items:
            # 更新监控目标为db_type对应的cmdb拓扑，其中标签 NO_MONITOR_TARGET 的策略，无需添加监控目标
            objs = AppMonitorTopo.get_set_by_dbtype(db_type=db_type)
            if objs and "NO_MONITOR_TARGET" not in details["labels"]:
                item["target"] = [
                    [
                        {
                            "field": "host_topo_node",
                            "method": "eq",
                            "value": [{"bk_inst_id": obj["bk_set_id"], "bk_obj_id": "set"} for obj in objs],
                        }
                    ]
                ]

            for query_config in item["query_configs"]:
                # data_type_label: time_series | event(自定义上报，需要填充data_id)
                # 自定义事件/指标类告警，需要渲染模板变量
                bkm_dbm_report_event = bkm_dbm_report["event"]
                bkm_dbm_report_metric = bkm_dbm_report["metric"]
                if "metric_id" in query_config:
                    try:
                        query_config["metric_id"] = query_config["metric_id"].format(
                            bk_biz_id=env.DBA_APP_BK_BIZ_ID,
                            event_data_id=bkm_dbm_report_event["data_id"],
                            metric_data_id=bkm_dbm_report_metric["data_id"],
                        )
                    except ValueError:
                        logger.exception(f"format metric_id error, {query_config['metric_id']}")
                if "result_table_id" in query_config:
                    query_config["result_table_id"] = query_config["result_table_id"].format(
                        bk_biz_id=env.DBA_APP_BK_BIZ_ID,
                        event_data_id=bkm_dbm_report_event["data_id"],
                        metric_data_id=bkm_dbm_report_metric["data_id"],
                    )

        return details

    def patch_priority_and_agg_conditions(self, details):
        """将监控目标映射为所有查询的where条件"""

        self.calc_from_targets()

        # patch priority
        details["priority"] = self.target_priority

        # patch agg conditions
        agg_conditions = []
        for target in self.targets:
            if target["level"] == TargetLevel.PLATFORM.value:
                continue

            target_rule = target["rule"]
            agg_conditions.append(
                {
                    "key": target_rule["key"],
                    "dimension_name": TargetLevel.get_choice_label(target_rule["key"]),
                    "value": target_rule["value"],
                    "method": "eq",
                    "condition": "and",
                }
            )

        # dbm 仅允许修改子策略的阈值，因此有修改时，需要先同步父亲的，再进行后续的 patch
        if self.parent_id != 0:
            parent_policy = MonitorPolicy.objects.get(id=self.parent_id)
            details["items"] = copy.deepcopy(parent_policy.details["items"])

        for item in details["items"]:
            for query_config in item["query_configs"]:
                if "agg_condition" in query_config:
                    # remove same type conditions
                    exclude_keys = list(map(lambda x: x["key"], self.custom_conditions)) + TargetLevel.get_values()
                    query_config_agg_condition = list(
                        filter(lambda cond: cond["key"] not in exclude_keys, query_config["agg_condition"])
                    )
                    query_config_agg_condition.extend(agg_conditions)
                    query_config_agg_condition.extend(self.custom_conditions)

                    # overwrite agg_condition
                    query_config["agg_condition"] = query_config_agg_condition
                else:
                    key_values = {}
                    for target in self.targets:
                        if target["level"] == TargetLevel.PLATFORM.value:
                            continue

                        target_rule = target["rule"]
                        key, values = target_rule["key"], target_rule["value"]
                        key_values[key] = values

                    query_config["promql"] = render_promql_sql(query_config["promql"], key_values)
                    logger.info("query_config.promql: %s", query_config["promql"])

        return details

    def patch_algorithms(self, details):
        """检测条件"""

        for rule in self.test_rules:
            rule["type"] = "Threshold"
            rule.pop("id", None)

        for item in details["items"]:
            item["algorithms"] = self.test_rules

        return details

    def patch_notice(self, details):
        """通知规则和通知对象"""
        # notify_rules -> notice.signal
        details["notice"]["signal"] = self.notify_rules

        # 克隆出来的策略，固定通知模式为：直接通知
        if self.parent_id:
            details["notice"]["options"]["assign_mode"] = ["only_notice"]

        # notice_groups -> notice.user_groups
        details["notice"]["user_groups"] = NoticeGroup.get_monitor_groups(group_ids=self.notify_groups)

        return details

    def local_save(self, *args, **kwargs):
        """仅保存到本地，不同步到监控"""
        super().save(*args, **kwargs)

    def patch_all(self):
        # model.targets -> agg_condition
        details = self.patch_priority_and_agg_conditions(self.details)

        # model.test_rules -> algorithms
        details = self.patch_algorithms(details)

        # model.notify_xxx -> notice
        details = self.patch_notice(details)

        # other
        details = self.patch_bk_biz_id(details)
        details = self.patch_target_and_metric_id(details, self.db_type)

        return details

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        """保存策略对象的同时，同步记录到监控"""

        # step1. sync to model
        # 启停操作(["is_enabled"]) -> 跳过重复的patch
        details = self.details if update_fields == ["is_enabled"] else self.patch_all()

        # step2. sync to bkm
        res = bkm_save_alarm_strategy(details)

        # overwrite by bkm strategy details
        self.details = res
        self.monitor_policy_id = self.details["id"]
        self.sync_at = datetime.datetime.now(timezone.utc)

        # 平台内置策略支持保存初始版本，用于恢复默认设置
        if self.pk is None and self.bk_biz_id == env.DBA_APP_BK_BIZ_ID:
            self.parent_details = self.details

        # 父策略有变更时，把子策略也刷新一遍，以保证子策略的配置与父策略的指标、维度、周期一致，才能够使优先级计算生效
        if self.parent_id == 0:
            for sub_policy in MonitorPolicy.objects.filter(parent_id=self.id):
                sub_policy.save()

        # step3. save to db
        super().save(force_insert, force_update, using, update_fields)

    def delete(self, using=None, keep_parents=False):
        """删除策略的同时，同步删除监控策略"""
        if self.monitor_policy_id:
            bkm_delete_alarm_strategy(self.monitor_policy_id)

        super().delete(using, keep_parents)

    def enable(self) -> bool:
        """启用：
        is_enabled:true -> save
        监控提供了批量启停的接口，若我们需要批量操作，这里可以切换接口为：
        推荐：update_partial_strategy_v3({
            "bk_biz_id":1,
            "ids":[23121],
            "edit_data":{
                "is_enabled":true,
                "notice_group_list":[4644]
            }
        })
        switch_alarm_strategy({"ids": [1], "is_enalbed": true/false})
        """
        self.is_enabled = True
        self.details.update(is_enabled=self.is_enabled)
        self.save(update_fields=["is_enabled"])

        return self.is_enabled

    def disable(self) -> bool:
        """禁用：is_enabled:false -> save"""
        self.is_enabled = False
        self.details.update(is_enabled=self.is_enabled)
        self.save(update_fields=["is_enabled"])

        return self.is_enabled

    @classmethod
    def clone(cls, params, username="system") -> dict:
        """克隆：patch -> create"""

        # params -> model
        policy = cls(**params)

        # transfer details from parent to self
        parent = cls.objects.get(id=policy.parent_id)

        policy.parent_details = copy.deepcopy(parent.details)
        policy.db_type = parent.db_type
        policy.monitor_indicator = parent.monitor_indicator

        policy.details = copy.deepcopy(parent.details)
        policy.details.pop("id", None)
        policy.details.update(name=policy.name, is_enabled=True)

        policy.creator = policy.updater = username
        policy.id = None

        policy.save()

        # 重新获取policy
        policy.refresh_from_db()

        return {"local_id": policy.id, "bkm_id": policy.monitor_policy_id}

    def update(self, params, username="system") -> dict:
        """更新：patch -> update"""

        update_fields = ["targets", "test_rules", "notify_rules", "notify_groups"]

        # param -> model
        for key in update_fields:
            setattr(self, key, params[key])

        # 可选参数
        if "custom_conditions" in params:
            self.custom_conditions = params["custom_conditions"]

        # update -> overwrite details
        self.creator = self.updater = username
        self.save()

        return {"local_id": self.id, "bkm_id": self.monitor_policy_id}

    def parse_details(self, details=None):
        """从模板反向提取部分参数"""

        details = details or self.details
        result = defaultdict(list)

        result["test_rules"] = [
            {
                "level": alg["level"],
                "config": alg["config"],
                "type": alg["type"],
                "unit_prefix": alg["unit_prefix"],
            }
            # 这里假设item长度恒为1
            for alg in details["items"][0]["algorithms"]
        ]

        first_query_config = details["items"][0]["query_configs"][0]
        target_conditions = (
            list(filter(lambda cond: cond["key"] in TargetLevel.get_values(), first_query_config["agg_condition"]))
            if "agg_condition" in first_query_config
            else []
        )

        result["targets"] = [
            {"level": condition["key"], "rule": {"key": condition["key"], "value": condition["value"]}}
            for condition in target_conditions
        ]

        # 默认填充平台级目标
        if not result["targets"]:
            result["targets"].append(
                {"level": TargetLevel.PLATFORM.value, "rule": {"key": TargetLevel.PLATFORM.value, "value": []}}
            )

        result["notify_rules"] = details["notice"]["signal"]
        result["notify_groups"] = list(
            NoticeGroup.objects.filter(monitor_group_id__in=details["notice"]["user_groups"])
            .values_list("id", flat=True)
            .distinct()
        )

        return result

    def reset(self) -> dict:
        """恢复默认：parent_details -> save"""

        # patch by parent details
        self.details = self.parent_details
        self.details["id"] = self.monitor_policy_id
        self.details["name"] = self.name

        # fetch targets/test_rules/notify_rules/notify_groups from parent details
        for attr, value in self.parse_details().items():
            setattr(self, attr, value)

        self.save()

        return {"local_id": self.id, "bkm_id": self.monitor_policy_id}

    @classmethod
    def get_policies(cls, db_type, bk_biz_id=PLAT_BIZ_ID):
        """获取监控策略id列表"""
        policy_ids = list(
            cls.objects.filter(db_type=db_type, bk_biz_id=bk_biz_id).values_list("monitor_policy_id", flat=True)
        )
        # MySQL 需额外补充
        if db_type == DBType.MySQL:
            policy_ids.extend(
                list(
                    cls.objects.filter(details__labels__contains=["/DBM_TBINLOGDUMPER/"]).values_list(
                        "monitor_policy_id", flat=True
                    )
                )
            )
        return policy_ids

    @classmethod
    def get_dispatch_policies(cls):
        """获取需独立分派的特殊策略"""
        return list(
            cls.objects.filter(details__labels__contains=["/DBM_NEED_DISPATCH/"]).values_list(
                "monitor_policy_id", flat=True
            )
        )

    @classmethod
    def sync_plat_monitor_policy(cls, action_id=None, db_type=None, force=False):
        if action_id is None:
            action_id = get_dbm_autofix_action_id()
        skip_dir = "v1"
        now = datetime.datetime.now(timezone.utc)
        logger.warning("[sync_plat_monitor_policy] sync bkm alarm policy start: %s", now)

        # 逐个json导入，本地+远程
        updated_policies = 0
        for root, dirs, files in os.walk(TPLS_ALARM_DIR):
            if skip_dir in dirs:
                dirs.remove(skip_dir)

            for alarm_tpl in files:

                with open(os.path.join(root, alarm_tpl), "r", encoding="utf-8") as f:
                    logger.info("[sync_plat_monitor_policy] start sync bkm alarm tpl: %s " % alarm_tpl)
                    try:
                        template_dict = json.loads(f.read())
                        # 监控API不支持传入额外的字段
                        template_dict.pop("export_at", "")
                        policy_name = template_dict["name"]
                    except json.decoder.JSONDecodeError:
                        logger.error("[sync_plat_monitor_policy] load template failed: %s", alarm_tpl)
                        continue

                    # 如指定db_type，只同步指定db_type的策略(跳过非指定db_type的策略)
                    if db_type is not None and template_dict.get("db_type") != db_type:
                        continue

                    deleted = template_dict.pop("deleted", False)

                    if not template_dict.get("details"):
                        logger.error(("[sync_plat_monitor_policy] template %s has no details" % alarm_tpl))
                        continue

                    # patch template
                    labels = list(set(template_dict["details"]["labels"]))
                    template_dict["details"]["labels"] = labels
                    template_dict["details"]["name"] = policy_name
                    template_dict["details"]["priority"] = TargetPriority.PLATFORM.value
                    # 平台策略仅开启基于分派通知
                    template_dict["details"]["notice"]["options"]["assign_mode"] = ["by_rule"]
                    for label in labels:
                        if label.startswith("NEED_AUTOFIX") and action_id is not None:
                            template_dict["details"]["actions"] = [
                                {
                                    "config_id": action_id,
                                    "signal": ["abnormal"],
                                    "user_groups": [],
                                    "options": {
                                        "converge_config": {
                                            "is_enabled": False,
                                            "converge_func": "skip_when_success",
                                            "timedelta": 60,
                                            "count": 1,
                                        }
                                    },
                                }
                            ]

                    policy = MonitorPolicy(**template_dict)

                policy_name = policy.name
                logger.info("[sync_plat_monitor_policy] start sync bkm alarm policy: %s " % policy_name)
                try:
                    synced_policy = MonitorPolicy.objects.get(bk_biz_id=policy.bk_biz_id, name=policy_name)

                    if deleted:
                        logger.info("[sync_plat_monitor_policy] delete old alarm: %s " % policy_name)
                        synced_policy.delete()
                        continue

                    if synced_policy.version >= policy.version and not force:
                        logger.info("[sync_plat_monitor_policy] skip same version alarm: %s " % policy_name)
                        continue

                    for keeped_field in MonitorPolicy.KEEPED_FIELDS:
                        setattr(policy, keeped_field, getattr(synced_policy, keeped_field))

                    policy.details["id"] = synced_policy.monitor_policy_id
                    logger.info("[sync_plat_monitor_policy] update bkm alarm policy: %s " % policy_name)
                except MonitorPolicy.DoesNotExist:
                    logger.info("[sync_plat_monitor_policy] create bkm alarm policy: %s " % policy_name)

                try:
                    # fetch targets/test_rules/notify_rules/notify_groups from parent details
                    for attr, value in policy.parse_details().items():
                        setattr(policy, attr, value)

                    policy.save()
                    updated_policies += 1
                    logger.error("[sync_plat_monitor_policy] save bkm alarm policy success: %s", policy_name)
                except BkMonitorSaveAlarmException as e:
                    logger.error("[sync_plat_monitor_policy] save bkm alarm policy failed: %s, %s ", policy_name, e)

        logger.warning(
            "[sync_plat_monitor_policy] finish sync bkm alarm policy end: %s, update_cnt: %s",
            datetime.datetime.now(timezone.utc) - now,
            updated_policies,
        )

    @staticmethod
    def bkm_search_event(
        bk_biz_ids: list,
        strategy_id: list,
        event_status: list = None,
        days=7,
        level=None,
        data_source=None,
        time_range=None,
        group_count=True,
    ):
        """事件搜索
        bk_biz_ids:[2] 必填

        id: 事件ID
        strategy_id: 事件关联的策略ID
        days: 查询最近几天内的时间，这个参数存在，time_range则失效
        time_range:"2020-02-26 00:00:00 -- 2020-02-28 23:59:59"
        conditions:
            level - 告警级别
                1 - 致命
                2 - 预警
                3 - 提醒
            event_status - 事件状态
                ABNORMAL - 未恢复
                CLOSED - 已关闭
                RECOVERED - 已恢复
            data_source: ["bk_monitor|time_series"]
                数据类型:
                time_series - 时序数据
                event - 事件
                log - 日志关键字
        返回格式:
         {
            "status": "ABNORMAL",
            "bk_biz_id": 2,
            "is_ack": false,
            "level": 1,
            "origin_alarm": {
              "data": {
                "record_id": "d751713988987e9331980363e24189ce.1574439900",
                "values": {
                  "count": 10,
                  "dtEventTimeStamp": 1574439900
                },
                "dimensions": {},
                "value": 10,
                "time": 1574439900
              },
              "trigger": {
                "level": "1",
                "anomaly_ids": [
                  "d751713988987e9331980363e24189ce.15744396",
                ]
              },
              "anomaly": {
                "1": {
                  "anomaly_message": "count >= 1.0, 当前值10.0",
                  "anomaly_time": "2019-11-22 16:31:06",
                  "anomaly_id": "d751713988987e9331980363e24189ce.1574439"
                }
              },
              "dimension_translation": {},
              "strategy_snapshot_key": "bk_bkmonitor.ee.cache.strategy.snapshot.88."
            },
            "target_key": "",
            "strategy_id": 88,
            "id": 1364253,
            "is_shielded": false,
            "event_id": "d751713988987e9331980363e24189ce.15744396",
            "create_time": "2019-11-22 16:31:07",
            "end_time": null,
            "begin_time": "2019-11-22 16:25:00",
            "origin_config": {},
            "p_event_id": ""
          }
        ]
        """

        # 默认搜索未恢复
        event_status = event_status or ["ABNORMAL"]
        condition_kwargs = {
            "strategy_id": strategy_id,
            "event_status": event_status,
            "level": level,
            "data_source": data_source,
        }

        # TODO: 单次查询上限5000条，若需要突破上限，需要循环查询
        params = {
            "bk_biz_ids": bk_biz_ids,
            "conditions": [
                {"key": cond_key, "value": cond_value}
                for cond_key, cond_value in condition_kwargs.items()
                if cond_value
            ],
            "days": days,
            "page": 1,
            "page_size": 5000,
        }

        # 精确范围查找
        if time_range:
            params["time_range"] = time_range
            params.pop("days")

        events = BKMonitorV3Api.search_event(params)

        # 需要根据app_id来拆分全局内置策略的告警数量
        if group_count:
            tmp = defaultdict(int)
            for event in events:
                app_id = event["origin_alarm"]["data"]["dimensions"].get("appid") or 0
                # 缺少业app_id维度的策略
                if not app_id:
                    logger.error("find bad appid event: %s", json.dumps(event))

                tmp[(event["strategy_id"], app_id)] += 1

            event_counts = defaultdict(dict)
            for (strategy_id, appid), event_count in tmp.items():
                event_counts[strategy_id][appid] = event_count
            return event_counts

        return events
