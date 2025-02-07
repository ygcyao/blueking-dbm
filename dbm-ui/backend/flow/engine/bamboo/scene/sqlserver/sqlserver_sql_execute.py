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
import logging.config
from dataclasses import asdict
from typing import Dict, Optional

from django.utils.translation import ugettext as _

from backend import env
from backend.configuration.constants import DBType
from backend.db_meta.enums import InstanceRole
from backend.db_meta.models import Cluster
from backend.exceptions import ValidationError
from backend.flow.consts import DBM_SQLSERVER_JOB_LONG_TIMEOUT, DEFAULT_SQLSERVER_PATH, SQlCmdFileFormatNOMap
from backend.flow.engine.bamboo.scene.common.builder import Builder, SubBuilder
from backend.flow.engine.bamboo.scene.common.get_file_list import GetFileList
from backend.flow.engine.bamboo.scene.sqlserver.base_flow import BaseFlow
from backend.flow.plugins.components.collections.sqlserver.create_random_job_user import SqlserverAddJobUserComponent
from backend.flow.plugins.components.collections.sqlserver.drop_random_job_user import SqlserverDropJobUserComponent
from backend.flow.plugins.components.collections.sqlserver.exec_actuator_script import SqlserverActuatorScriptComponent
from backend.flow.plugins.components.collections.sqlserver.trans_files import TransFileInWindowsComponent
from backend.flow.utils.sqlserver.sqlserver_act_dataclass import (
    CreateRandomJobUserKwargs,
    DownloadMediaKwargs,
    DropRandomJobUserKwargs,
    ExecActuatorKwargs,
)
from backend.flow.utils.sqlserver.sqlserver_act_payload import SqlserverActPayload
from backend.flow.utils.sqlserver.sqlserver_db_function import create_sqlserver_login_sid
from backend.flow.utils.sqlserver.sqlserver_host import Host

logger = logging.getLogger("flow")


class SqlserverSQLExecuteFlow(BaseFlow):
    """
    构建Sqlserver执行SQL文件的流程类
    兼容跨云集群的执行
    """

    def __init__(self, root_id: str, data: Optional[Dict]):
        super().__init__(root_id, data)
        self.sql_target_path = f"{DEFAULT_SQLSERVER_PATH}\\SqlFile_{data['uid']}\\"

    def __get_sql_files(self) -> list:
        """
        拼接待下发的SQL文件列表
        """
        file_list = []
        for obj in self.data["execute_objects"]:
            sql_files = obj.get("sql_files", [])
            if not sql_files:
                raise ValidationError("param execute_objects error: sql_files is null")

            for sql_file in sql_files:
                file_list.append(f"{env.BKREPO_PROJECT}/{env.BKREPO_BUCKET}/{self.data['path']}/{sql_file}")

        # 做一下去重返回
        return list(filter(None, list(set(file_list))))

    def run_flow(self):
        """
        定义SQL脚本执行流程，执行多集群并发执行；多SQL文件顺序执行
        执行逻辑：
        1: 下发执行器
        2: 下发SQL文件
        3: 执行SQL文件
        """
        # 定义主流程
        main_pipeline = Builder(root_id=self.root_id, data=self.data)
        sub_pipelines = []

        clusters = Cluster.objects.filter(id__in=self.data["cluster_ids"])

        if len(clusters) == 0 or len(clusters) != len(self.data["cluster_ids"]):
            raise Exception(f"cluster not found: cluster_ids[{self.data['cluster_ids']}]")

        # 合并下发需要变更的文件，不同的bk_cloud_id需要分组处理
        target_hosts = [
            Host(
                ip=c.storageinstance_set.get(
                    instance_role__in=[InstanceRole.ORPHAN, InstanceRole.BACKEND_MASTER]
                ).machine.ip,
                bk_cloud_id=c.bk_cloud_id,
            )
            for c in clusters
        ]
        act_lists = [
            {
                "act_name": _("下发db-actuator介质"),
                "act_component_code": TransFileInWindowsComponent.code,
                "kwargs": asdict(
                    DownloadMediaKwargs(
                        target_hosts=target_hosts,
                        file_list=GetFileList(db_type=DBType.Sqlserver).get_db_actuator_package(),
                    )
                ),
            },
            {
                "act_name": _("下发SQL文件"),
                "act_component_code": TransFileInWindowsComponent.code,
                "kwargs": asdict(
                    DownloadMediaKwargs(
                        target_hosts=target_hosts,
                        file_list=self.__get_sql_files(),
                        file_target_path=self.sql_target_path,
                    )
                ),
            },
        ]

        main_pipeline.add_parallel_acts(acts_list=act_lists)

        for cluster in clusters:
            # 获取当前cluster的主节点,每个集群有且只有一个master/orphan 实例
            master_instance = cluster.storageinstance_set.get(
                instance_role__in=[InstanceRole.ORPHAN, InstanceRole.BACKEND_MASTER]
            )

            # 拼接全局上下文
            sub_flow_context = copy.deepcopy(self.data)
            sub_flow_context["sql_target_path"] = self.sql_target_path
            sub_flow_context["ports"] = [master_instance.port]
            sub_flow_context["charset_no"] = SQlCmdFileFormatNOMap[self.data["charset"]]

            # 声明子流程
            sub_pipeline = SubBuilder(root_id=self.root_id, data=copy.deepcopy(sub_flow_context))

            # 创建随机账号
            sub_pipeline.add_act(
                act_name=_("create temp job account"),
                act_component_code=SqlserverAddJobUserComponent.code,
                kwargs=asdict(
                    CreateRandomJobUserKwargs(
                        cluster_ids=[cluster.id],
                        sid=create_sqlserver_login_sid(),
                    ),
                ),
            )

            # 执行SQL文件,默认3小时超时
            sub_pipeline.add_act(
                act_name=_("执行SQL导入"),
                act_component_code=SqlserverActuatorScriptComponent.code,
                kwargs=asdict(
                    ExecActuatorKwargs(
                        exec_ips=[Host(ip=master_instance.machine.ip, bk_cloud_id=cluster.bk_cloud_id)],
                        get_payload_func=SqlserverActPayload.get_execute_sql_payload.__name__,
                        job_timeout=DBM_SQLSERVER_JOB_LONG_TIMEOUT,
                    )
                ),
            )

            # 删除随机账号
            sub_pipeline.add_act(
                act_name=_("remove temp job account"),
                act_component_code=SqlserverDropJobUserComponent.code,
                kwargs=asdict(DropRandomJobUserKwargs(cluster_ids=[cluster.id])),
            )

            sub_pipelines.append(sub_pipeline.build_sub_process(sub_name=_("{}SQL文件导入".format(cluster.name))))

        main_pipeline.add_parallel_sub_pipeline(sub_flow_list=sub_pipelines)
        main_pipeline.run_pipeline()
