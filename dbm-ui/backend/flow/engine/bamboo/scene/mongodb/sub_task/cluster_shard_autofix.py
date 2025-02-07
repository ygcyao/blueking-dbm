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

from copy import deepcopy
from typing import Dict, Optional

from django.utils.translation import ugettext as _

from backend.flow.consts import MongoDBClusterRole
from backend.flow.engine.bamboo.scene.common.builder import SubBuilder
from backend.flow.engine.bamboo.scene.mongodb.mongodb_install import install_plugin
from backend.flow.engine.bamboo.scene.mongodb.mongodb_install_dbmon import add_install_dbmon
from backend.flow.plugins.components.collections.mongodb.exec_actuator_job import ExecuteDBActuatorJobComponent
from backend.flow.plugins.components.collections.mongodb.mongodb_cmr_4_meta import CMRMongoDBMetaComponent
from backend.flow.plugins.components.collections.mongodb.send_media import ExecSendMediaOperationComponent
from backend.flow.utils.mongodb.mongodb_dataclass import ActKwargs

from .cluster_mongod_autofix import mongod_autofix


def shard_autofix(
    root_id: str, ticket_data: Optional[Dict], sub_kwargs: ActKwargs, info: dict, cluster_role: str
) -> SubBuilder:
    """
    shard自愈流程
    info 表示replicaset信息
    """

    # 获取变量
    sub_get_kwargs = deepcopy(sub_kwargs)

    # 创建子流程
    sub_pipeline = SubBuilder(root_id=root_id, data=ticket_data)

    # 获取信息
    sub_get_kwargs.get_host_cluster_autofix(info=info)

    # 安装蓝鲸插件
    install_plugin(pipeline=sub_pipeline, get_kwargs=sub_get_kwargs, new_cluster=False)

    # 介质下发
    kwargs = sub_get_kwargs.get_send_media_kwargs(media_type="all")
    sub_pipeline.add_act(
        act_name=_("MongoDB-介质下发"), act_component_code=ExecSendMediaOperationComponent.code, kwargs=kwargs
    )

    # 创建原子任务执行目录
    kwargs = sub_get_kwargs.get_create_dir_kwargs()
    sub_pipeline.add_act(
        act_name=_("MongoDB-创建原子任务执行目录"), act_component_code=ExecuteDBActuatorJobComponent.code, kwargs=kwargs
    )

    # 机器初始化
    kwargs = sub_get_kwargs.get_os_init_kwargs()
    sub_pipeline.add_act(
        act_name=_("MongoDB-机器初始化"), act_component_code=ExecuteDBActuatorJobComponent.code, kwargs=kwargs
    )

    # 进行替换——并行 以ip为维度
    sub_sub_pipelines = []
    for mongodb_instance in info["instances"]:
        sub_get_kwargs.db_instance = mongodb_instance
        sub_sub_pipeline = mongod_autofix(
            root_id=root_id,
            ticket_data=ticket_data,
            sub_sub_kwargs=sub_get_kwargs,
            cluster_role=cluster_role,
            info=info,
        )
        sub_sub_pipelines.append(sub_sub_pipeline)
    sub_pipeline.add_parallel_sub_pipeline(sub_sub_pipelines)

    # 修改db_meta数据
    info["created_by"] = sub_get_kwargs.payload.get("created_by")
    info["bk_biz_id"] = sub_get_kwargs.payload.get("bk_biz_id")
    if cluster_role == MongoDBClusterRole.ShardSvr.value:
        info["db_type"] = "cluster_mongodb"
        name = "shard"
    elif cluster_role == MongoDBClusterRole.ConfigSvr.value:
        info["db_type"] = "mongo_config"
        name = "configDB"
        # 修改所有mongos的configDB ip
        kwargs = sub_get_kwargs.get_change_config_ip_kwargs(info=info)
        sub_pipeline.add_act(
            act_name=_("MongoDB--mongos修改configDB参数"),
            act_component_code=ExecuteDBActuatorJobComponent.code,
            kwargs=kwargs,
        )
    kwargs = sub_get_kwargs.get_change_meta_replace_kwargs(info=info, instance={})
    sub_pipeline.add_act(
        act_name=_("MongoDB-mongod修改meta"), act_component_code=CMRMongoDBMetaComponent.code, kwargs=kwargs
    )

    # 安装dbmon
    ip_list = sub_get_kwargs.payload["plugin_hosts"]
    exec_ips = [host["ip"] for host in ip_list]
    add_install_dbmon(
        root_id=root_id,
        flow_data=ticket_data,
        pipeline=sub_sub_pipeline,
        iplist=exec_ips,
        bk_cloud_id=ip_list[0]["bk_cloud_id"],
        allow_empty_instance=True,
    )

    return sub_pipeline.build_sub_process(sub_name=_("MongoDB--{}自愈--ip:{}".format(name, info["ip"])))
