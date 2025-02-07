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
from collections import defaultdict

from celery import current_app
from celery.schedules import crontab
from django.core.cache import cache
from django.utils import timezone

from backend import env
from backend.components import BKMonitorV3Api
from backend.constants import CACHE_CLUSTER_STATS
from backend.db_meta.enums import ClusterType
from backend.db_meta.models import Cluster
from backend.db_periodic_task.local_tasks import register_periodic_task, start_new_span
from backend.db_periodic_task.local_tasks.db_meta.constants import (
    QUERY_TEMPLATE,
    SAME_QUERY_TEMPLATE_CLUSTER_TYPE_MAP,
    UNIFY_QUERY_PARAMS,
)
from backend.db_periodic_task.utils import TimeUnit, calculate_countdown

logger = logging.getLogger("celery")


def query_cap(bk_biz_id, cluster_type, cap_key="used"):
    """查询某类集群的某种容量: used/total"""

    cluster_type = SAME_QUERY_TEMPLATE_CLUSTER_TYPE_MAP.get(cluster_type, cluster_type)
    query_template = QUERY_TEMPLATE.get(cluster_type)
    if not query_template:
        logger.error("No query template for cluster type: %s", cluster_type)
        return {}

    # now-5/15m ~ now
    end_time = datetime.datetime.now(timezone.utc)
    start_time = end_time - datetime.timedelta(minutes=query_template["range"])

    params = copy.deepcopy(UNIFY_QUERY_PARAMS)

    # mysql 的指标不连续，使用 "type": "instant" 会导致查询结果为空
    if cluster_type in [ClusterType.TenDBSingle.value, ClusterType.TenDBHA.value, ClusterType.TenDBCluster.value]:
        params.pop("type", "")

    params["bk_biz_id"] = env.DBA_APP_BK_BIZ_ID
    params["start_time"] = int(start_time.timestamp())
    params["end_time"] = int(end_time.timestamp())

    params["query_configs"][0]["promql"] = query_template[cap_key] % f'appid="{bk_biz_id}"'
    series = BKMonitorV3Api.unify_query(params)["series"]

    cluster_bytes = {}
    for serie in series:
        # 集群：cluster_domain | influxdb: instance_host
        cluster_domain = list(serie["dimensions"].values())[0]
        datapoints = list(filter(lambda dp: dp[0] is not None, serie["datapoints"]))

        if not datapoints:
            logger.info("No datapoints for cluster: %s -> %s", cluster_domain, serie["datapoints"])
            continue
        cluster_bytes[cluster_domain] = datapoints[-1][0]

    return cluster_bytes


def query_cluster_capacity(bk_biz_id, cluster_type):
    """查询集群容量"""

    cluster_cap_bytes = defaultdict(dict)

    domains = list(
        Cluster.objects.filter(bk_biz_id=bk_biz_id, cluster_type=cluster_type)
        .values_list("immute_domain", flat=True)
        .distinct()
    )

    used_data = query_cap(bk_biz_id, cluster_type, "used")
    for cluster, used in used_data.items():
        # 排除无效集群
        if cluster not in domains:
            continue
        cluster_cap_bytes[cluster]["used"] = used

    total_data = query_cap(bk_biz_id, cluster_type, "total")
    for cluster, used in total_data.items():
        # 排除无效集群
        if cluster not in domains:
            continue
        cluster_cap_bytes[cluster]["total"] = used

    return cluster_cap_bytes


@current_app.task
def sync_cluster_stat_by_cluster_type(bk_biz_id, cluster_type):
    """
    按集群类型同步各集群容量状态
    """

    logger.info("sync_cluster_stat_from_monitor started")
    try:
        cluster_stats = query_cluster_capacity(bk_biz_id, cluster_type)
    except Exception as e:
        logger.error("query_cluster_capacity error: %s -> %s", cluster_type, e)
        return

    # 计算使用率
    for cluster, cap in cluster_stats.items():
        # 兼容查不到数据的情况
        if not ("used" in cap and "total" in cap):
            continue
        cap["in_use"] = round(cap["used"] * 100.0 / cap["total"], 2)

    cache.set(
        f"{CACHE_CLUSTER_STATS}_{bk_biz_id}_{cluster_type}", json.dumps(cluster_stats), timeout=2 * TimeUnit.HOUR
    )

    return cluster_stats


@register_periodic_task(run_every=crontab(hour="*/1", minute=0))
def sync_cluster_stat_from_monitor():
    """
    同步各集群容量状态
    """

    logger.info("sync_cluster_stat_from_monitor started")
    biz_cluster_types = Cluster.objects.values_list("bk_biz_id", "cluster_type").distinct()

    count = len(biz_cluster_types)
    for index, (bk_biz_id, cluster_type) in enumerate(biz_cluster_types):
        countdown = calculate_countdown(count=count, index=index, duration=1 * TimeUnit.HOUR)
        logger.info(
            "{}_{} sync_cluster_stat_from_monitor will be run after {} seconds.".format(
                bk_biz_id, cluster_type, countdown
            )
        )
        with start_new_span(sync_cluster_stat_by_cluster_type):
            sync_cluster_stat_by_cluster_type.apply_async(
                kwargs={"bk_biz_id": bk_biz_id, "cluster_type": cluster_type}, countdown=countdown
            )
