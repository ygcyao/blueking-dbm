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
import logging.config
from typing import Dict, Optional

from django.utils.translation import ugettext as _

from backend.flow.engine.bamboo.scene.common.builder import Builder
from backend.flow.engine.bamboo.scene.mongodb.sub_task.instance_deinstall import instance_deinstall
from backend.flow.plugins.components.collections.mongodb.exec_actuator_job import ExecuteDBActuatorJobComponent
from backend.flow.plugins.components.collections.mongodb.send_media import ExecSendMediaOperationComponent
from backend.flow.utils.mongodb.mongodb_dataclass import ActKwargs

logger = logging.getLogger("flow")


class MongoInstanceDeInstallFlow(object):
    """MongoDB实例卸载flow"""

    def __init__(self, root_id: str, data: Optional[Dict]):
        """
        传入参数
        @param root_id : 任务流程定义的root_id
        @param data : 单据传递过来的参数列表，是dict格式
        """

        self.root_id = root_id
        self.data = data
        self.get_kwargs = ActKwargs()
        self.get_kwargs.payload = data
        self.get_kwargs.get_file_path()

    def multi_instance_deinstall_flow(self):
        """
        multi instance deinstall流程
        """

        # 创建流程实例
        pipeline = Builder(root_id=self.root_id, data=self.data)

        # 获取参数
        self.get_kwargs.get_host_instance_deinstall()

        # 介质下发——job的api可以多个IP并行执行
        kwargs = self.get_kwargs.get_send_media_kwargs(media_type="actuator")
        pipeline.add_act(
            act_name=_("MongoDB-介质下发"), act_component_code=ExecSendMediaOperationComponent.code, kwargs=kwargs
        )

        # 创建原子任务执行目录
        kwargs = self.get_kwargs.get_create_dir_kwargs()
        pipeline.add_act(
            act_name=_("MongoDB-创建原子任务执行目录"), act_component_code=ExecuteDBActuatorJobComponent.code, kwargs=kwargs
        )

        # 复制集整机替换——子流程并行
        sub_pipelines = []
        for instance in self.data["infos"]:
            sub_pipline = instance_deinstall(
                root_id=self.root_id,
                ticket_data=self.data,
                sub_kwargs=self.get_kwargs,
                info=instance,
            )
            sub_pipelines.append(sub_pipline)
        pipeline.add_parallel_sub_pipeline(sub_flow_list=sub_pipelines)

        # 运行流程
        pipeline.run_pipeline()
