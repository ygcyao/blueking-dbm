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
from celery.schedules import crontab

from backend.db_periodic_task.local_tasks import register_periodic_task
from backend.db_services.taskflow import task as TaskFlow
from backend.ticket.tasks.ticket_tasks import TicketTask


@register_periodic_task(run_every=5)
def auto_retry_exclusive_inner_flow():
    TicketTask.retry_exclusive_inner_flow()


# 数据修复跳过周一，因为周一取得checksum是上周五记录，会造成修复失效
@register_periodic_task(run_every=crontab(minute=0, hour=6, day_of_week="0,2,3,4,5,6"))
def auto_create_data_repair_ticket():
    TicketTask.auto_create_data_repair_ticket()


@register_periodic_task(run_every=crontab(minute="*/1"))
def clean_bamboo_engine_expired_data():
    TaskFlow.clean_bamboo_engine_expired_data()


@register_periodic_task(run_every=crontab(hour="*/1", minute=0))
def auto_clear_expire_flow():
    TicketTask.auto_clear_expire_flow()
