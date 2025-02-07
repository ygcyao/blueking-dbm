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

from celery import shared_task

from backend import env
from backend.components import BKMonitorV3Api
from backend.configuration.constants import PLAT_BIZ_ID
from backend.exceptions import ApiResultError

logger = logging.getLogger("celery")


@shared_task
def update_app_policy(bk_biz_id, notify_group_id, db_type):
    """业务监控策略刷新
    当业务运维配置了业务dba时，可调用该task立即下发策略更新
    notify_group_id: 新建的蓝鲸告警组
    """
    from .models import MonitorPolicy, NoticeGroup

    if not notify_group_id:
        logger.error("update_app_policy skip empty notify_group_id: %s", notify_group_id)
        return

    logger.warning(
        "update_app_policy start bk_biz_id=%s, notify_group_id=%s, db_type=%s", bk_biz_id, notify_group_id, db_type
    )

    # TODO: 批量更新，不太适合自定义策略，告警组很难做聚合
    # policies = MonitorPolicy.get_policies(db_type, bk_biz_id)
    # BKMonitorV3Api.update_partial_strategy_v3({
    #     "ids": policies,
    #     "edit_data": {
    #         "notice_group_list": [
    #             monitor_group_id
    #         ]
    #     },
    #     "bk_biz_id": env.DBA_APP_BK_BIZ_ID
    # })

    if bk_biz_id == PLAT_BIZ_ID:
        logger.error("update_app_policy skip built in policy of %s", bk_biz_id)
        return

    # 逐个策略更新
    for policy in MonitorPolicy.objects.filter(db_type=db_type, bk_biz_id=bk_biz_id):
        plat_groups = NoticeGroup.get_groups(PLAT_BIZ_ID, id_name="id")
        plat_group_id = plat_groups.get(policy.db_type)

        old_notify_groups = copy.deepcopy(policy.notify_groups)

        # 移除平台告警组
        if plat_group_id in policy.notify_groups:
            try:
                policy.notify_groups.remove(plat_group_id)
            except ValueError:
                pass

        # 添加目标告警组
        if notify_group_id not in policy.notify_groups:
            policy.notify_groups.append(notify_group_id)

        if set(policy.notify_groups) != set(old_notify_groups):
            logger.warning(
                "update_app_policy update policy=%s, notify_group_id=%s, db_type=%s: %s -> %s",
                policy.name,
                notify_group_id,
                db_type,
                old_notify_groups,
                policy.notify_groups,
            )
            policy.save()
        else:
            logger.warning(
                "update_app_policy skip policy=%s, notify_group_id=%s, db_type=%s",
                policy.name,
                notify_group_id,
                db_type,
            )


@shared_task
def update_db_notice_group(db_type: str):
    """更新DB类型的告警组"""
    from backend.db_monitor.models import NoticeGroup

    for notice_group in NoticeGroup.objects.filter(is_built_in=True, db_type=db_type):
        logger.info("[local_notice_group] update notice group: %s", notice_group.name)
        notice_group.save()


@shared_task
def delete_monitor_duty_rule(db_type: str, monitor_duty_rule_id):
    """解绑相关告警组，删除轮值策略，调用此函数之前保证轮值已从DBM中删除"""
    update_db_notice_group(db_type)

    logger.info("[duty_rule] delete duty rule: %s", monitor_duty_rule_id)

    try:
        BKMonitorV3Api.delete_duty_rules({"ids": [monitor_duty_rule_id], "bk_biz_ids": [env.DBA_APP_BK_BIZ_ID]})
    except (ApiResultError, Exception) as e:
        # 轮值删除错误暂可忽略，因为删除之前已经停用不会生效，并且在DBM数据也清理。只是会在监控平台留下一条脏数据
        logger.error("[duty_rule] error in deleting duty: %s", e)
