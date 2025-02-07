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

from celery.schedules import crontab

from backend.db_periodic_task.local_tasks.register import register_periodic_task

from .check_binlog_backup import check_binlog_backup
from .check_full_backup import check_full_backup

logger = logging.getLogger("celery")


@register_periodic_task(run_every=crontab(minute=33, hour=2))
def mysql_backup_check_task():
    """
    mysql 全备巡检
    """
    check_full_backup("")


@register_periodic_task(run_every=crontab(minute=15, hour=2))
def mysql_binlog_check_task():
    """
    mysql binlog巡检
    """
    check_binlog_backup("")
