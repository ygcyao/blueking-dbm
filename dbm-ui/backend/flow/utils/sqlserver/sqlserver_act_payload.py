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

from django.utils.translation import ugettext as _

from backend.configuration.constants import DBType
from backend.db_package.models import Package
from backend.env import WINDOW_SSH_PORT
from backend.flow.consts import SQLSERVER_CUSTOM_SYS_USER, DBActuatorTypeEnum, MediumEnum, SqlserverActuatorActionEnum
from backend.flow.utils.sqlserver.payload_handler import PayloadHandler
from backend.flow.utils.sqlserver.sqlserver_bk_config import (
    get_module_infos,
    get_sqlserver_alarm_config,
    get_sqlserver_config,
)

logger = logging.getLogger("flow")


class SqlserverActPayload(PayloadHandler):
    def system_init_payload(self, **kwargs) -> dict:
        """
        系统初始化payload
        """
        payload = {"ssh_port": WINDOW_SSH_PORT}
        return {
            "db_type": DBActuatorTypeEnum.Default.value,
            "action": SqlserverActuatorActionEnum.SysInit.value,
            "payload": {**self.get_init_system_account(), **payload},
        }

    @staticmethod
    def check_mssql_service_payload(self, **kwargs) -> dict:
        """
        测试实例是否注册存在的payload
        """
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver_check.value,
            "action": SqlserverActuatorActionEnum.MssqlServiceCheck.value,
            "payload": {},
        }

    def get_install_sqlserver_payload(self, **kwargs) -> dict:
        """
        拼接安装sqlserver的payload参数, 分别兼容集群申请、集群实例重建、集群实例添加单据的获取方式
        """
        # 获取对应DB模块的信息
        db_module = get_module_infos(
            bk_biz_id=int(self.global_data["bk_biz_id"]),
            db_module_id=int(self.global_data["db_module_id"]),
            cluster_type=self.global_data["cluster_type"],
        )
        # 获取安装包信息
        sqlserver_pkg = Package.get_latest_package(
            version=db_module["db_version"],
            pkg_type=MediumEnum.Sqlserver,
            db_type=DBType.Sqlserver,
        )
        # 获取版本对应的key,如果为空则报异常
        install_key = self.get_version_key(db_module["db_version"])
        if not install_key:
            raise Exception(_("找不到对应版本的install key"))

        # 拼接每个端口的配置
        init_sqlserver_config = {}

        for cluster in self.global_data["clusters"]:
            init_sqlserver_config[cluster["port"]] = get_sqlserver_config(
                bk_biz_id=int(self.global_data["bk_biz_id"]),
                immutable_domain=cluster["immutable_domain"],
                db_module_id=int(self.global_data["db_module_id"]),
                db_version=db_module["db_version"],
                cluster_type=self.global_data["cluster_type"],
            )

        install_ports = self.global_data["install_ports"]
        if not isinstance(install_ports, list) or len(init_sqlserver_config) == 0:
            raise Exception(_("传入的安装sqlserver端口列表为空或者非法值，请联系系统管理员: install_ports {}".format(install_ports)))

        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.Deploy.value,
            "payload": {
                "general": {"runtime_account": self.get_create_sqlserver_account(self.global_data["bk_cloud_id"])},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "pkg": sqlserver_pkg.name,
                    "pkg_md5": sqlserver_pkg.md5,
                    "charset": db_module["charset"],
                    "sqlserver_version": db_module["db_version"],
                    "install_key": install_key,
                    "max_remain_mem_gb": int(db_module["max_remain_mem_gb"]),
                    "buffer_percent": int(db_module["buffer_percent"]),
                    "ports": install_ports,
                    "sqlserver_configs": copy.deepcopy(init_sqlserver_config),
                },
            },
        }

    def get_init_sqlserver_payload(self, **kwargs) -> dict:
        """
        拼接初始化sqlserver的payload参数
        """
        # 获取对应DB模块的信息
        db_module = get_module_infos(
            bk_biz_id=int(self.global_data["bk_biz_id"]),
            db_module_id=int(self.global_data["db_module_id"]),
            cluster_type=self.global_data["cluster_type"],
        )
        if not isinstance(self.global_data["install_ports"], list):
            raise Exception(
                _("传入的安装sqlserver端口列表为空或者非法值，请联系系统管理员: install_ports {}".format(self.global_data["install_ports"]))
            )

        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.Init.value,
            "payload": {
                "general": {"runtime_account": self.get_create_sqlserver_account(self.global_data["bk_cloud_id"])},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "pkg": "test",
                    "pkg_md5": "00000000000000000000000000000000",
                    "charset": db_module["charset"],
                    "sqlserver_version": db_module["db_version"],
                    "install_key": "test",
                    "max_remain_mem_gb": int(db_module["max_remain_mem_gb"]),
                    "buffer_percent": int(db_module["buffer_percent"]),
                    "ports": self.global_data["install_ports"],
                    "sqlserver_configs": {},
                    "init_sql": get_sqlserver_alarm_config(
                        bk_biz_id=int(self.global_data["bk_biz_id"]),
                        cluster_domain=self.global_data["clusters"][0]["immutable_domain"],
                        db_module_id=int(self.global_data["db_module_id"]),
                        is_only_init_sql=True,
                    ).get("init_sql", ""),
                },
            },
        }

    def get_execute_sql_payload(self, **kwargs) -> dict:
        """
        执行SQL文件的payload
        """
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.ExecSQLFiles.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "ports": self.global_data["ports"],
                    "charset_no": self.global_data["charset_no"],
                    "file_path": self.global_data["sql_target_path"],
                    "execute_objects": self.global_data["execute_objects"],
                },
            },
        }

    def get_backup_dbs_payload(self, **kwargs) -> dict:
        """
        执行数据库备份的payload
        """
        if self.global_data.get("is_recalc_sync_dbs", False):
            backup_dbs = kwargs["trans_data"]["sync_dbs"]
        else:
            backup_dbs = self.global_data["backup_dbs"]

        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.BackupDBS.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": kwargs["custom_params"]["port"],
                    "backup_dbs": backup_dbs,
                    "backup_type": kwargs["custom_params"]["backup_type"],
                    "job_id": self.global_data["job_id"],
                    "file_tag": kwargs["custom_params"]["file_tag"],
                    "is_set_full_model": self.global_data.get("is_set_full_model", False),
                    "target_backup_dir": self.global_data.get("target_backup_dir", ""),
                },
            },
        }

    def get_rename_dbs_payload(self, **kwargs) -> dict:
        """
        执行数据库重命名的payload
        """
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.RenameDBS.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": self.global_data["port"],
                    "rename_dbs": self.global_data["rename_infos"],
                    "slaves": self.global_data["slaves"],
                    "sync_mode": self.global_data["sync_mode"],
                },
            },
        }

    def get_clean_dbs_payload(self, **kwargs) -> dict:
        """
        执行数据库清档的payload
        """
        if self.global_data.get("is_recalc_clean_dbs", False):
            clean_dbs = kwargs["trans_data"]["clean_dbs"]
        else:
            clean_dbs = self.global_data["clean_dbs"]
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.CleanDBS.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": self.global_data["port"],
                    "clean_dbs": clean_dbs,
                    "sync_mode": self.global_data["sync_mode"],
                    "clean_mode": self.global_data["clean_mode"],
                    "slaves": self.global_data["slaves"],
                    "clean_tables": self.global_data["clean_tables"],
                    "ignore_clean_tables": self.global_data["ignore_clean_tables"],
                    "is_force": kwargs["custom_params"].get("is_force", False),
                },
            },
        }

    def get_switch_payload(self, **kwargs) -> dict:
        """
        执行互切或者故障转移的payload
        """
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.RoleSwitch.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": self.global_data["port"],
                    "master_host": self.global_data["master_host"],
                    "master_port": self.global_data["master_port"],
                    "force": self.global_data["force"],
                    "sync_mode": self.global_data["sync_mode"],
                    "other_slaves": self.global_data["other_slaves"],
                },
            },
        }

    def get_check_abnormal_db_payload(self, **kwargs) -> dict:
        """
        检查实例是否存在非正常状态的数据
        """
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver_check.value,
            "action": SqlserverActuatorActionEnum.CheckAbnormalDB.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": self.global_data["port"],
                },
            },
        }

    def get_check_inst_process_payload(self, **kwargs) -> dict:
        """
        检查实例是否存在业务连接
        """
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver_check.value,
            "action": SqlserverActuatorActionEnum.CheckInstProcess.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": self.global_data["port"],
                    "is_force_kill": kwargs["custom_params"].get("is_force_kill", False),
                },
            },
        }

    def get_clone_user_payload(self, **kwargs) -> dict:
        """
        实例之间克隆用户
        """

        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.CloneLoginUsers.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": self.global_data["port"],
                    "source_host": self.global_data["source_host"],
                    "source_port": self.global_data["source_port"],
                    "system_logins": SQLSERVER_CUSTOM_SYS_USER,
                },
            },
        }

    def get_clone_jobs_payload(self, **kwargs) -> dict:
        """
        实例之间克隆作业
        """
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.CloneJobs.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": self.global_data["port"],
                    "source_host": self.global_data["source_host"],
                    "source_port": self.global_data["source_port"],
                },
            },
        }

    def get_clone_linkserver_payload(self, **kwargs) -> dict:
        """
        实例之间克隆linkserver配置
        """
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.CloneLinkservers.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": self.global_data["port"],
                    "source_host": self.global_data["source_host"],
                    "source_port": self.global_data["source_port"],
                },
            },
        }

    def get_restore_full_dbs_payload(self, **kwargs) -> dict:
        """
        恢复全量备份的payload
        """
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.RestoreDBSForFull.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": kwargs["custom_params"]["port"],
                    "restore_infos": kwargs["custom_params"]["restore_infos"],
                    "restore_mode": kwargs["custom_params"].get("restore_mode", ""),
                },
            },
        }

    def get_restore_log_dbs_payload(self, **kwargs) -> dict:
        """
        恢复增量备份的payload
        """
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.RestoreDBSForLog.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": kwargs["custom_params"]["port"],
                    "restore_infos": kwargs["custom_params"]["restore_infos"],
                    "restore_mode": kwargs["custom_params"].get("restore_mode", ""),
                    "restore_time": kwargs["custom_params"].get("restore_time", ""),
                },
            },
        }

    def get_build_database_mirroring(self, **kwargs) -> dict:
        """
        建立数据库级别镜像关系的payload
        """
        if self.global_data.get("is_recalc_sync_dbs", False):
            sync_dbs = kwargs["trans_data"]["sync_dbs"]
        else:
            sync_dbs = kwargs["custom_params"]["dbs"]

        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.BuildDBMirroring.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": self.global_data["port"],
                    "dr_host": kwargs["custom_params"]["dr_host"],
                    "dr_port": kwargs["custom_params"]["dr_port"],
                    "dbs": sync_dbs,
                },
            },
        }

    def get_build_add_dbs_in_always_on(self, **kwargs) -> dict:
        """
        建立数据库加入always_on可用组的payload
        """
        if self.global_data.get("is_recalc_sync_dbs", False):
            sync_dbs = kwargs["trans_data"]["sync_dbs"]
        else:
            sync_dbs = kwargs["custom_params"]["dbs"]

        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.AddDBSInAlwaysOn.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": self.global_data["port"],
                    "add_slaves": kwargs["custom_params"]["add_slaves"],
                    "dbs": sync_dbs,
                },
            },
        }

    def get_build_always_on(self, **kwargs) -> dict:
        """
        建立实例加入always_on可用组的payload
        """
        if kwargs["custom_params"]["is_use_sa"]:
            runtime_account = self.get_sa_account()
        else:
            runtime_account = self.get_sqlserver_account()

        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.BuildAlwaysOn.value,
            "payload": {
                "general": {"runtime_account": runtime_account},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": kwargs["custom_params"]["port"],
                    "add_slaves": kwargs["custom_params"]["add_slaves"],
                    "group_name": kwargs["custom_params"]["group_name"],
                    "is_first": kwargs["custom_params"].get("is_first", True),
                },
            },
        }

    def get_init_machine_for_always_on(self, **kwargs) -> dict:
        """
        建立always_on可用组之前初始化机器的payload
        """
        if kwargs["custom_params"]["is_use_sa"]:
            runtime_account = self.get_sa_account()
        else:
            runtime_account = self.get_sqlserver_account()
        print(kwargs["custom_params"].get("is_first", True))
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.InitForAlwaysOn.value,
            "payload": {
                "general": {"runtime_account": runtime_account},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": kwargs["custom_params"]["port"],
                    "add_members": kwargs["custom_params"]["add_members"],
                    "is_first": kwargs["custom_params"].get("is_first", True),
                },
            },
        }

    def uninstall_sqlserver(self, **kwargs) -> dict:
        """
        卸载sqlserver的payload
        """
        if kwargs["custom_params"].get("is_use_sa"):
            runtime_account = self.get_sa_account()
        else:
            runtime_account = self.get_sqlserver_account()
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.Uninstall.value,
            "payload": {
                "general": {"runtime_account": runtime_account},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "ports": kwargs["custom_params"]["ports"],
                    "force": kwargs["custom_params"].get("force", False),
                },
            },
        }

    def check_backup_file_is_in_local(self, **kwargs) -> dict:
        """
        移动备份文件
        """
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.MoveBackupFile.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "target_path": kwargs["custom_params"]["target_path"],
                    "file_list": kwargs["custom_params"]["file_list"],
                },
            },
        }

    def init_instance_for_dbm(self, **kwargs) -> dict:
        """
        接入DBM初始化实例
        """
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.InitSqlserverInstance.value,
            "payload": {
                "general": {"runtime_account": self.get_create_sqlserver_account(self.global_data["bk_cloud_id"])},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": kwargs["custom_params"]["port"],
                },
            },
        }

    def get_clear_config_payload(self, **kwargs) -> dict:
        """
        执行清理实例配置的payload，例如清理Job、LinkServer
        """
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.ClearConfig.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": kwargs["custom_params"]["port"],
                    "is_clear_job": kwargs["custom_params"]["is_clear_job"],
                    "is_clear_linkserver": kwargs["custom_params"]["is_clear_linkserver"],
                },
            },
        }

    def get_remote_dr_payload(self, **kwargs) -> dict:
        """
        移除AlwaysOn可用组
        """
        return {
            "db_type": DBActuatorTypeEnum.Sqlserver.value,
            "action": SqlserverActuatorActionEnum.RemoteDr.value,
            "payload": {
                "general": {"runtime_account": self.get_sqlserver_account()},
                "extend": {
                    "host": kwargs["ips"][0]["ip"],
                    "port": kwargs["custom_params"]["port"],
                    "remotes_slaves": kwargs["custom_params"]["remotes_slaves"],
                },
            },
        }
