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
import os.path
from collections import defaultdict

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import ugettext as _

from backend import env
from backend.components import CCApi, JobApi
from backend.configuration.constants import DBType
from backend.db_meta.enums import ClusterPhase, ClusterType
from backend.db_meta.models import (
    AppCache,
    Cluster,
    ClusterEntry,
    Machine,
    NosqlStorageSetDtl,
    ProxyInstance,
    StorageInstance,
    StorageInstanceTuple,
    TenDBClusterSpiderExt,
)
from backend.db_services.ipchooser.constants import DB_MANAGE_SET
from backend.db_services.ipchooser.query import resource
from backend.flow.utils.cc_manage import CcManage
from backend.utils.string import base64_encode

logger = logging.getLogger("root")

SNIPPETS_DIR = os.path.join(settings.BASE_DIR, "scripts/snippets")


def remove_cluster(cluster_id, job_clean=True, cc_clean=True):
    """移除主机+job清理+cc清理"""

    logger.info("Removing cluster: %s, job_clean=%s, cc_clean=%s", cluster_id, job_clean, cc_clean)

    cluster = Cluster.objects.get(pk=cluster_id)
    cluster.phase = ClusterPhase.OFFLINE
    cluster.save()

    db_type = ClusterType.cluster_type_to_db_type(cluster.cluster_type)

    cluster_ips = set(
        list(cluster.storageinstance_set.values_list("machine__ip", flat=True))
        + list(cluster.proxyinstance_set.values_list("machine__ip", flat=True))
    )
    cluster_bk_host_ids = set(
        list(cluster.storageinstance_set.values_list("machine__bk_host_id", flat=True))
        + list(cluster.proxyinstance_set.values_list("machine__bk_host_id", flat=True))
    )

    # 相关系统清理
    if job_clean:
        try:
            with open(os.path.join(SNIPPETS_DIR, f"uninstall_{db_type}.sh"), "r") as f:
                script_content = f.read()

            JobApi.fast_execute_script(
                {
                    "bk_biz_id": env.JOB_BLUEKING_BIZ_ID,
                    "script_content": base64_encode(script_content),
                    "task_name": _("清理集群"),
                    "account_alias": "root",
                    "script_language": 1,
                    "target_server": {
                        "ip_list": [{"bk_cloud_id": cluster.bk_cloud_id, "ip": ip} for ip in cluster_ips]
                    },
                },
                raw=True,
            )

        except Exception as e:  # pylint: disable=broad-except
            logger.error("drop_cluster job_clean exception: cluster_id=%s, %s", cluster_id, e)

    if cc_clean and cluster_bk_host_ids:
        cc_manage = CcManage(cluster.bk_biz_id, cluster.cluster_type)
        try:
            cc_manage.recycle_host(list(cluster_bk_host_ids))
        except Exception as e:  # pylint: disable=broad-except
            logger.error("drop_cluster cc_clean exception: cluster_id=%s, %s", cluster_id, e)

        cc_manage.delete_cluster_modules(db_type, cluster)

    cluster.nosqlstoragesetdtl_set.all().delete()
    cluster.storageinstance_set.all().delete()
    cluster.proxyinstance_set.all().delete()

    cluster.clusterentry_set.all().update(forward_to=None)
    cluster.clusterentry_set.all().delete()
    Machine.objects.filter(ip__in=cluster_ips).delete()
    cluster.delete()


def remove_all_cluster(job_clean=True, cc_clean=True):
    """清理所有集群"""

    # 正常清理
    for cluster in Cluster.objects.all():
        try:
            remove_cluster(cluster.id, job_clean, cc_clean)
        except Exception as err:
            logger.error(f"failed to clean cluster {cluster.id}, {err}")

    # 异常收尾
    NosqlStorageSetDtl.objects.all().delete()
    ProxyInstance.objects.all().delete()
    StorageInstance.objects.all().delete()
    Machine.objects.all().delete()
    ClusterEntry.objects.all().delete()
    StorageInstanceTuple.objects.all().delete()
    Cluster.objects.all().delete()


def remove_cluster_ips(bk_host_ids, job_clean=True, cc_clean=True):
    """移除主机+job清理+cc清理"""

    logger.info("Removing bk_host_ids: %s, job_clean=%s, cc_clean=%s", bk_host_ids, job_clean, cc_clean)

    storage_instances = StorageInstance.objects.filter(machine__ip__in=bk_host_ids)
    proxy_instances = ProxyInstance.objects.filter(machine__ip__in=bk_host_ids)

    # 相关系统清理
    if job_clean:
        for db_type in DBType.get_values():
            try:
                with open(os.path.join(SNIPPETS_DIR, f"uninstall_{db_type}.sh"), "r") as f:
                    script_content = f.read()

                JobApi.fast_execute_script(
                    {
                        "bk_biz_id": env.JOB_BLUEKING_BIZ_ID,
                        "script_content": base64_encode(script_content),
                        "task_name": _("清理集群"),
                        "account_alias": "root",
                        "script_language": 1,
                        "host_id_list": bk_host_ids,
                    },
                    raw=True,
                )

            except Exception as e:  # pylint: disable=broad-except
                logger.error("remove_bk_host_ids job_clean exception: bk_host_ids=%s, %s", bk_host_ids, e)

    if cc_clean and bk_host_ids:
        try:
            CCApi.transfer_host_to_recyclemodule(
                {"bk_biz_id": env.DBA_APP_BK_BIZ_ID, "bk_host_id": bk_host_ids}, use_admin=True, raw=True
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("remove_bk_host_ids cc_clean exception: bk_host_ids=%s, %s", bk_host_ids, e)

        CcManage(env.DBA_APP_BK_BIZ_ID, "").update_host_properties(bk_host_ids=bk_host_ids)

    storage_instances.delete()
    TenDBClusterSpiderExt.objects.filter(instance__machine__bk_host_id__in=bk_host_ids).delete()
    proxy_instances.delete()
    Machine.objects.filter(bk_host_id__in=bk_host_ids).delete()


def clean_cc_topo(bk_biz_id=env.DBA_APP_BK_BIZ_ID):
    """清理dbm的cc拓扑"""

    manage_set_id = CCApi.search_set(
        {"bk_biz_id": env.DBA_APP_BK_BIZ_ID, "condition": {"bk_set_name": DB_MANAGE_SET}}
    )["info"][0]["bk_set_id"]

    # 排除default非0的模块(内置模块）
    res = CCApi.search_module({"bk_biz_id": bk_biz_id, "condition": {"default": 0}})
    # 查询模块下的主机数量
    host_topo_relations = resource.ResourceQueryHelper.fetch_host_topo_relations(env.DBA_APP_BK_BIZ_ID)

    bk_module_ip_counts = defaultdict(int)
    for host_topo_relation in host_topo_relations:
        # 暂不统计非缓存数据，遇到不一致的情况需要触发缓存更新
        bk_module_ip_counts[host_topo_relation["bk_module_id"]] += 1

    bk_modules = res["info"]
    for bk_module in bk_modules:
        if bk_module_ip_counts[bk_module["bk_module_id"]] > 0:
            continue

        if bk_module["bk_set_id"] == manage_set_id:
            continue

        # 清理空模块
        logger.info("delete empty module -> {bk_module_id}:{bk_module_name}".format(**bk_module))
        CCApi.delete_module(
            {
                "bk_biz_id": env.DBA_APP_BK_BIZ_ID,
                "bk_set_id": bk_module["bk_set_id"],
                "bk_module_id": bk_module["bk_module_id"],
            }
        )


def cache_appcache_data(sender, **kwargs):
    try:
        data = AppCache.objects.all().values()
        appcache_list = list(data) if data else []
        appcache_dict = {app["bk_biz_id"]: app for app in data}
        # 默认30min过期，稍微晚于周期同步cc拓扑的定时任务(20min)
        timeout = 60 * 30
        cache.set("appcache_list", appcache_list, timeout=timeout)
        cache.set("appcache_dict", appcache_dict, timeout=timeout)
    except Exception as e:
        logger.info(f"cache_appcache error: {e}")
