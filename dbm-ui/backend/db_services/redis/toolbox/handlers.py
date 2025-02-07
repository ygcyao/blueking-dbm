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
import json

from django.db import connection

from backend.components import DRSApi
from backend.db_meta.enums import InstanceRole
from backend.db_meta.enums.comm import RedisVerUpdateNodeType
from backend.db_meta.exceptions import InstanceNotExistException
from backend.db_meta.models import Cluster
from backend.db_services.dbbase.cluster.handlers import ClusterServiceHandler
from backend.db_services.ipchooser.handlers.host_handler import HostHandler
from backend.db_services.ipchooser.query.resource import ResourceQueryHelper
from backend.db_services.redis.redis_modules.models import TbRedisModuleSupport
from backend.db_services.redis.redis_modules.models.redis_module_support import ClusterRedisModuleAssociate
from backend.db_services.redis.resources.constants import SQL_QUERY_COUNT_INSTANCES, SQL_QUERY_INSTANCES
from backend.db_services.redis.resources.redis_cluster.query import RedisListRetrieveResource
from backend.exceptions import ApiResultError
from backend.flow.utils.base.payload_handler import PayloadHandler
from backend.flow.utils.redis.redis_proxy_util import (
    get_cluster_proxy_version,
    get_cluster_proxy_version_for_upgrade,
    get_cluster_redis_version,
    get_cluster_remote_address,
    get_cluster_storage_versions_for_upgrade,
)
from backend.utils.basic import dictfetchall


class ToolboxHandler(ClusterServiceHandler):
    """redis工具箱查询接口封装"""

    def __init__(self, bk_biz_id: int):
        super().__init__(bk_biz_id)

    def query_cluster_ips(
        self, limit=None, offset=None, cluster_id=None, ip=None, role=None, status=None, cluster_status=None
    ):
        """聚合查询集群下的主机 TODO:"""

        limit_sql = ""
        if limit and limit > 0:
            # 强制格式化为int，避免sql注入
            limit_sql = " LIMIT {}".format(int(limit))

        offset_sql = ""
        if offset:
            offset_sql = " OFFSET {}".format(int(offset))

        where_sql = "WHERE i.bk_biz_id = %s "
        where_values = [self.bk_biz_id]

        if cluster_id:
            placeholder = ",".join(["%s"] * len(cluster_id))
            where_sql += f"AND c.cluster_id IN ({placeholder})"
            where_values.extend(cluster_id)

        if ip:
            ip_conditions = " OR ".join(["m.ip LIKE %s" for _ in ip])
            where_sql += f" AND ({ip_conditions})"
            where_ip_values = [f"%{single_ip}%" for single_ip in ip]
            where_values.extend(where_ip_values)

        if status:
            where_sql += "AND i.status = %s "
            where_values.append(status)
            # placeholders = ",".join(["%s"] * len(status))
            # where_sql += "AND i.status IN (" + placeholders + ") "
            # where_values.extend(status)

        if cluster_status:
            where_sql += "AND cluster.status = %s "
            where_values.append(cluster_status)

        if role:
            placeholder = ", ".join(["%s"] * len(role))
            having_sql = f"HAVING role IN ({placeholder}) "
            where_values.extend(role)
        else:
            having_sql = ""

        # union查询需要两份参数
        where_values = where_values * 2
        sql_count = SQL_QUERY_COUNT_INSTANCES.format(where=where_sql, having=having_sql)
        sql = SQL_QUERY_INSTANCES.format(where=where_sql, having=having_sql, limit=limit_sql, offset=offset_sql)

        with connection.cursor() as cursor:
            cursor.execute(sql_count, where_values)
            total_count = cursor.fetchone()[0]
            cursor.execute(sql, where_values)

        ips = dictfetchall(cursor)
        bk_host_ids = [ip["bk_host_id"] for ip in ips]

        if not bk_host_ids:
            return {"count": 0, "results": ips}

        # 查询主机信息
        host_id_info_map = {host["host_id"]: host for host in HostHandler.check([], [], [], bk_host_ids)}

        # 查询主从状态对
        master_slave_map = RedisListRetrieveResource.query_master_slave_map(
            [i["ip"] for i in ips if i["role"] == InstanceRole.REDIS_MASTER]
        )
        cloud_info = ResourceQueryHelper.search_cc_cloud(get_cache=True)
        # 补充主机、规格和主从关系信息、补充云区域信息
        for item in ips:
            item["host_info"] = host_id_info_map.get(item["bk_host_id"])
            item["spec_config"] = json.loads(item["spec_config"])
            item["bk_cloud_name"] = cloud_info[str(item["bk_cloud_id"])]["bk_cloud_name"]
            item.update(master_slave_map.get(item["ip"], {}))

        response = {"count": total_count, "results": ips}
        return response

    @classmethod
    def get_online_cluster_versions(cls, cluster_id: int, node_type: str):
        """根据cluster id获取集群现存版本"""
        if node_type == RedisVerUpdateNodeType.Backend.value:
            return [get_cluster_redis_version(cluster_id)]
        else:
            return get_cluster_proxy_version(cluster_id)

    @classmethod
    def get_update_cluster_versions(cls, cluster_id: int, node_type: str):
        """根据cluster类型获取版本信息"""
        if node_type == RedisVerUpdateNodeType.Backend.value:
            return get_cluster_storage_versions_for_upgrade(cluster_id)
        else:
            return get_cluster_proxy_version_for_upgrade(cluster_id)

    @classmethod
    def webconsole_rpc(cls, cluster_id: int, cmd: str, db_num: int = 0, raw: bool = True, **kwargs):
        """
        执行webconsole命令，只支持select语句
        @param cluster_id: 集群ID
        @param cmd: 执行命令
        @param db_num: 数据库编号
        @param raw: 源字符返回
        """
        cluster = Cluster.objects.get(id=cluster_id)
        # 获取访问密码
        password = PayloadHandler.redis_get_cluster_password(cluster=cluster)["redis_proxy_password"]
        # 获取rpc结果
        try:
            remote_address = get_cluster_remote_address(cluster_id=cluster.id)
            rpc_results = DRSApi.redis_rpc(
                {
                    "bk_cloud_id": cluster.bk_cloud_id,
                    "addresses": [remote_address],
                    "command": cmd,
                    "db_num": db_num,
                    "raw": raw,
                    "password": password,
                    # redis这里的client_type固定为webconsole，drs会发起redis-cli进行执行
                    "client_type": "webconsole",
                }
            )
        except (ApiResultError, InstanceNotExistException) as err:
            return {"query": "", "error_msg": err.message}

        return {"query": rpc_results[0]["result"], "error_msg": ""}

    @classmethod
    def get_cluster_module_info(cls, cluster_id: int, version: str):
        """
        获取集群module信息
        """
        # 获取版本支持的module名称列表
        support_modules = TbRedisModuleSupport.objects.filter(major_version=version).values_list(
            "module_name", flat=True
        )
        # 获取集群已安装的module名称列表
        cluster_module_associate = ClusterRedisModuleAssociate.objects.filter(cluster_id=cluster_id).first()
        cluster_modules = getattr(cluster_module_associate, "module_names", [])
        # 字典输出集群是否安装的module列表
        results = {item: (item in cluster_modules) for item in support_modules}
        return {"results": results}
