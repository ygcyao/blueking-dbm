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
import importlib
import json
import logging
import os
from typing import Callable, Dict

from django.utils.translation import ugettext as _
from rest_framework import serializers

from backend import env
from backend.components.dbresource.client import DBResourceApi
from backend.configuration.constants import DBType, SystemSettingsEnum
from backend.configuration.models import BizSettings, DBAdministrator, SystemSettings
from backend.db_dirty.constants import MachineEventType, PoolType
from backend.db_dirty.models import DirtyMachine, MachineEvent
from backend.db_meta.models import AppCache, Cluster
from backend.db_services.dbbase.constants import IpSource
from backend.flow.engine.controller.base import BaseController
from backend.iam_app.dataclass.actions import ActionEnum
from backend.ticket.constants import TICKET_EXPIRE_DEFAULT_CONFIG, FlowRetryType, FlowType, TicketType
from backend.ticket.models import Flow, Ticket, TicketFlowsConfig

logger = logging.getLogger("root")


class CallBackBuilderMixin(object):
    """为节点添加前置/后继钩子函数信息"""

    def __init__(self, ticket: Ticket):
        self.ticket = ticket

    def pre_callback(self):
        pass

    def post_callback(self):
        pass

    def add_common_params(self):
        self.ticket_data.update(
            {
                "uid": self.ticket.id,
                "ticket_type": self.ticket.ticket_type,
                "created_by": self.ticket.creator,
                "bk_biz_id": self.ticket.bk_biz_id,
            }
        )

    def build_callback_info(self) -> Dict:
        return {
            "pre_callback_module": self.pre_callback.__module__,
            "pre_callback_class": self.pre_callback.__qualname__.split(".")[0],
            "post_callback_module": self.post_callback.__module__,
            "post_callback_class": self.post_callback.__qualname__.split(".")[0],
        }

    def inject_callback_in_params(self, params: Dict = None) -> Dict:
        params = params or {}
        params.update({"callback_info": self.build_callback_info()})
        return params


class FlowParamBuilder(CallBackBuilderMixin):
    """
    Flow 参数构建器
    职责：将单据详情（ticket.details）转化为 Flow 流程运行所需的参数
    """

    # 配置任务流程控制器：流程启动函数
    controller = None

    def __init__(self, ticket: Ticket):
        self.ticket = ticket
        self.ticket_data = copy.deepcopy(ticket.details)

    def build_controller_info(self) -> dict:
        return {
            "func_name": self.controller.__name__,
            "class_name": self.controller.__qualname__.split(".")[0],
            "module": self.controller.__module__,
        }

    def format_ticket_data(self):
        """格式化单据数据，由子类实现"""
        pass

    def get_params(self) -> dict:
        self.add_common_params()
        self.format_ticket_data()

        params = {
            "ticket_data": copy.deepcopy(self.ticket_data),
            "controller_info": self.build_controller_info(),
        }
        params = super().inject_callback_in_params(params=params)

        if env.ENVIRONMENT == "dev":
            logger.info("flow.bamboo.params: \n%s\n", json.dumps(params, indent=2))

        return params


class ItsmParamBuilder(CallBackBuilderMixin):
    """
    ITSM 参数构建器
    职责：将单据详情（ticket.details）转化为 ITSM 单据创建所需的参数
    - 定义单据的审批人，默认取对应 DB 类型的管理员
    - 格式化单据概览，提高单据的可读性
    """

    def __init__(self, ticket: Ticket):
        self.ticket = ticket
        self.details = copy.deepcopy(ticket.details)

    def get_approvers(self):
        db_type = BuilderFactory.registry[self.ticket.ticket_type].group
        approvers = DBAdministrator.get_biz_db_type_admins(self.ticket.bk_biz_id, db_type)
        return ",".join(approvers)

    def format(self):
        pass

    def get_params(self):
        self.format()
        # clusters只是为了给服务单详情展示的信息，不需要在单据中体现
        cluster_domains = [cluster["immute_domain"] for cluster in self.details.pop("clusters", {}).values()]
        service_id = SystemSettings.get_setting_value(SystemSettingsEnum.BK_ITSM_SERVICE_ID.value)
        title = _("【DBM单据审批】{}").format(self.ticket.get_ticket_type_display())
        app = AppCache.objects.get(bk_biz_id=self.ticket.bk_biz_id)
        params = {
            "service_id": service_id,
            "creator": self.ticket.creator,
            "fields": [
                {"key": "title", "value": title},
                {"key": "app", "value": f"{app.bk_biz_name}(#{app.bk_biz_id}, {app.db_app_abbr})"},
                {"key": "domain", "value": "\n".join(cluster_domains)},
                {"key": "summary", "value": self.ticket.remark},
                {"key": "approver", "value": self.get_approvers()},
                {"key": "ticket_url", "value": self.ticket.iframe_url},
            ],
            "dynamic_fields": [],
            "meta": {
                "callback_url": f"{env.BK_SAAS_CALLBACK_URL}/apis/tickets/{self.ticket.id}/callback/",
                "state_processors": {},
            },
        }
        params = super().inject_callback_in_params(params=params)

        if env.ENVIRONMENT == "dev":
            logger.debug("flow.itsm.params: \n%s\n", json.dumps(params, indent=2))

        return params


class PauseParamBuilder(CallBackBuilderMixin):
    """
    Pause 参数构造器
    职责：为暂停任务提供单据参数
    预写参数:
     - pause_type: 可表示暂停的类型
    """

    def __init__(self, ticket: Ticket):
        self.ticket = ticket
        self.ticket_data = copy.deepcopy(ticket.details)
        self.params = {"pause_type": None}

    @property
    def operators(self):
        """当前单据指定处理人"""
        return []

    def format(self):
        """
        这里可以为params添加更多参数
        适配更加复杂的场景
        """
        pass

    def get_params(self):
        self.format()
        self.params.update(operators=self.operators)
        self.params = super().inject_callback_in_params(params=self.params)
        return self.params


class ResourceApplyParamBuilder(CallBackBuilderMixin):
    """
    ResourceApply资源申请 参数构造器
    职责：为资源申请提供额外参数，并为后继的inner flow节点更新信息
    """

    # 是否运行申请资源为空，运行的情况下跳过该item的资源申请
    allow_resource_empty: bool = False

    def __init__(self, ticket: Ticket):
        self.ticket = ticket
        self.ticket_data = copy.deepcopy(ticket.details)

    def format(self):
        """
        这里可以为params添加更多参数
        适配更加复杂的场景
        """
        pass

    def get_params(self):
        self.format()
        self.ticket_data.update(allow_resource_empty=self.allow_resource_empty)
        super().add_common_params()
        super().inject_callback_in_params(params=self.ticket_data)
        return self.ticket_data

    def post_callback(self):
        """
        部署单据需要有特殊的参数填充或者逻辑处理，
        需要在各自的ResourceApplyParamBuilder重写post_callback
        """
        pass

    def patch_info_affinity_location(self, roles=None):
        """
        批量节点变更的时候，补充亲和性和位置参数
        """
        from backend.ticket.builders.common.base import fetch_cluster_ids

        cluster_ids = fetch_cluster_ids(self.ticket_data["infos"])
        cluster_id_map = {cluster.id: cluster for cluster in Cluster.objects.filter(id__in=cluster_ids)}
        for info in self.ticket_data["infos"]:
            cluster = cluster_id_map[fetch_cluster_ids(info)[0]]
            self.patch_affinity_location(cluster, info["resource_spec"], roles)
            # 工具箱操作，补充业务和云区域ID
            info.update(bk_cloud_id=cluster.bk_cloud_id, bk_biz_id=self.ticket.bk_biz_id)

    @classmethod
    def patch_affinity_location(cls, cluster, resource_spec, roles=None):
        """
        节点变更的时候，补充亲和性和位置参数
        """
        resource_role = roles or resource_spec.keys()
        for role in resource_role:
            resource_spec[role]["affinity"] = cluster.disaster_tolerance_level
            resource_spec[role]["location_spec"] = {"city": cluster.region, "sub_zone_ids": []}


class RecycleParamBuilder(FlowParamBuilder):
    """
    回收主机流程 参数构建器
    职责：获取单据中的下架机器，并走回收流程
    """

    controller_map = {
        DBType.MySQL.value: "mysql.MySQLController.mysql_machine_clear_scene",
        DBType.TenDBCluster.value: "spider.SpiderController.tendbcluster_machine_clear_scene",
        DBType.Doris.value: "doris.DorisController.doris_machine_clear_scene",
        DBType.Kafka.value: "kafka.KafkaController.kafka_machine_clear_scene",
        DBType.Es.value: "es.EsController.es_machine_clear_scene",
        DBType.Hdfs.value: "hdfs.HdfsController.hdfs_machine_clear_scene",
        DBType.Pulsar.value: "pulsar.PulsarController.pulsar_machine_clear_scene",
        DBType.Vm.value: "vm.VmController.vm_machine_clear_scene",
        # TODO redis，sqlserver，mongo清理流程暂时没有
        DBType.Redis.value: "",
        DBType.Sqlserver.value: "",
        DBType.MongoDB.value: "",
    }

    def __init__(self, ticket: Ticket):
        super().__init__(ticket)
        self.ip_dest = self.ticket_data["ip_recycle"]["ip_dest"]
        assert self.ip_dest is not None

    def build_controller_info(self) -> dict:
        db_type = self.ticket_data["db_type"]
        # TODO: 暂时兼容没有清理流程的组件，默认用mysql
        clear_db_type = db_type if self.controller_map.get(db_type) else DBType.MySQL.value

        file_name, class_name, flow_name = self.controller_map[clear_db_type].split(".")
        module = importlib.import_module(f"backend.flow.engine.controller.{file_name}")
        self.controller = getattr(getattr(module, class_name), flow_name)

        return super().build_controller_info()

    def format_ticket_data(self):
        self.ticket_data = {
            "clear_hosts": self.ticket_data["recycle_hosts"],
            "ip_dest": self.ip_dest,
            # 一批机器的操作系统类型一致，任取一个即可
            "os_name": self.ticket_data["recycle_hosts"][0]["os_name"],
            "os_type": self.ticket_data["recycle_hosts"][0]["os_type"],
            "db_type": self.ticket.group,
        }

    def post_callback(self):
        # 转移到故障池，记录机器事件(如果是资源池则资源导入后会记录)
        ticket_data = self.ticket.current_flow().details["ticket_data"]
        if ticket_data["ip_dest"] != PoolType.Fault:
            return

        event = MachineEventType.ToFault
        bk_biz_id, recycle_hosts, operator = self.ticket.bk_biz_id, ticket_data["clear_hosts"], self.ticket.creator
        MachineEvent.host_event_trigger(bk_biz_id, recycle_hosts, event, operator, self.ticket, standard=True)


class ReImportResourceParamBuilder(FlowParamBuilder):
    """
    资源重导入流程 参数构造器 - 此流程目前仅用于回收后使用
    职责：获取单据中下架的机器，并走资源池导入流程
    """

    controller = BaseController.import_resource_init_step

    def __init__(self, ticket: Ticket):
        super().__init__(ticket)

    def format_ticket_data(self):
        recycle_hosts = self.ticket_data["recycle_hosts"]
        # 我们认为，在资源申请的情况下，不会混用多个集群类型
        self.ticket_data = {
            "ticket_id": self.ticket.id,
            "for_biz": self.ticket_data["ip_recycle"]["for_biz"],
            "resource_type": self.ticket.group,
            "os_type": recycle_hosts[0]["bk_os_type"],
            "hosts": recycle_hosts,
            "operator": self.ticket.creator,
            # 标记为退回
            "return_resource": True,
            # 要查询主机实际的业务管控
            "bk_biz_id": recycle_hosts[0]["bk_host_id"],
        }

    def pre_callback(self):
        # 在run的时候才会生成task id，此时要更新到资源池参数里面
        flow = self.ticket.current_flow()
        flow.update_details(task_id=flow.flow_obj_id)
        # 添加导入记录
        hosts = flow.details["ticket_data"]["hosts"]
        import_record = {"task_id": flow.flow_obj_id, "operator": self.ticket.creator, "hosts": hosts}
        DBResourceApi.import_operation_create(params=import_record)


class TicketFlowBuilder:
    """
    单据流程构建器
    职责：定义单据流程（ticket_flow），实例化单据流程对象并结合 FlowParamBuilder/ItsmParamBuilder 生成所需参数
    """

    ticket_type = None
    group = None
    serializer = None
    alarm_transform_serializer = None

    # 默认任务参数构造器
    inner_flow_name: str = ""
    inner_flow_builder: FlowParamBuilder = None
    # 默认暂停参数构造器
    pause_node_builder: PauseParamBuilder = PauseParamBuilder
    # 默认审批参数构造器
    itsm_flow_builder: ItsmParamBuilder = ItsmParamBuilder
    # 默认主机回收参数构造器
    recycle_flow_builder: RecycleParamBuilder = RecycleParamBuilder
    # 默认资源重导入参数构造器
    import_resource_flow_builder: ReImportResourceParamBuilder = ReImportResourceParamBuilder
    # 默认资源申请参数构造器
    # resource_apply_builder和resource_batch_apply_builder只能存在其一，表示是资源池单次申请还是批量申请
    resource_apply_builder: ResourceApplyParamBuilder = None
    resource_batch_apply_builder: ResourceApplyParamBuilder = None

    # inner flow互斥的重试类型，默认为手动重试
    retry_type: FlowRetryType = FlowRetryType.MANUAL_RETRY
    # 默认是否需要审批,人工确认。后续用于初始化单据配置表
    default_need_itsm: bool = True
    default_need_manual_confirm: bool = True
    # 默认过期时间配置
    default_expire_config: dict = TICKET_EXPIRE_DEFAULT_CONFIG
    # 是否用户可修改单据流程(在单据配置表中)
    editable: bool = True

    def __init__(self, ticket: Ticket):
        self.ticket = ticket

    @classmethod
    def name(cls):
        return cls.__name__

    @classmethod
    def type(cls):
        return cls.__name__.lower()

    @classmethod
    def enabled(cls) -> bool:
        """
        是否开启，默认开启
        可考虑使用功能开关控制
        """
        return True

    @property
    def ticket_configs(self):
        if not hasattr(self, "_ticket_configs"):
            from backend.ticket.builders.common.base import fetch_cluster_ids

            cluster_ids = fetch_cluster_ids(self.ticket.details)
            configs = TicketFlowsConfig.get_cluster_configs(self.ticket_type, self.ticket.bk_biz_id, cluster_ids)
            setattr(self, "_ticket_configs", configs)
        return getattr(self, "_ticket_configs")

    @property
    def need_itsm(self):
        """是否需要itsm审批节点。后续默认从单据配置表获取。子类可覆写，覆写以后editable为False"""
        need_itsm = any([c.configs["need_itsm"] for c in self.ticket_configs])
        return need_itsm

    @property
    def need_manual_confirm(self):
        """是否需要人工确认节点。后续默认从单据配置表获取。子类可覆写，覆写以后editable为False"""
        need_manual_confirm = any([c.configs["need_manual_confirm"] for c in self.ticket_configs])
        return need_manual_confirm

    @property
    def need_resource_pool(self):
        """是否存在资源池接入"""
        return self.ticket.details.get("ip_source") == IpSource.RESOURCE_POOL

    @property
    def need_recycle(self):
        """是否回收主机"""
        return self.ticket.details.get("ip_recycle", {}).get("ip_dest")

    def custom_ticket_flows(self):
        return []

    def init_ticket_flows(self):
        """
        自定义流程，默认流程是：
        单据审批(可选, 默认有) --> 人工确认(可选, 默认无) --> 资源申请(由单据参数判断) ---> inner节点 --> 资源交付(由单据参数判断)
        如果有特殊的flow需求，可在custom_ticket_flows中定制，会替换掉inner节点为custom流程
        对于复杂流程，可以直接覆写init_ticket_flows
        """
        flows = []

        # 判断并添加审批节点
        if self.need_itsm:
            flows.append(
                Flow(
                    ticket=self.ticket,
                    flow_type=FlowType.BK_ITSM.value,
                    details=self.itsm_flow_builder(self.ticket).get_params(),
                    flow_alias=_("单据审批"),
                )
            )

        # 判断并添加人工确认节点
        if self.need_manual_confirm:
            flows.append(
                Flow(
                    ticket=self.ticket,
                    flow_type=FlowType.PAUSE.value,
                    details=self.pause_node_builder(self.ticket).get_params(),
                    flow_alias=_("人工确认"),
                ),
            )

        # 判断并添加资源申请节点
        if self.need_resource_pool:
            if not self.resource_apply_builder:
                flow_type, resource_builder = FlowType.RESOURCE_BATCH_APPLY, self.resource_batch_apply_builder
            else:
                flow_type, resource_builder = FlowType.RESOURCE_APPLY, self.resource_apply_builder
            flows.append(
                Flow(
                    ticket=self.ticket,
                    flow_type=flow_type,
                    details=resource_builder(self.ticket).get_params(),
                    flow_alias=_("资源申请"),
                ),
            )

        # 若单据有特殊的自定义流程，则优先使用。否则使用默认的 inner_param_builder
        custom_ticket_flows = self.custom_ticket_flows()
        if custom_ticket_flows:
            flows.extend(custom_ticket_flows)
        else:
            flows.append(
                Flow(
                    ticket=self.ticket,
                    flow_type=FlowType.INNER_FLOW.value,
                    details=self.inner_flow_builder(self.ticket).get_params(),
                    flow_alias=self.inner_flow_name,
                    retry_type=self.retry_type,
                )
            )

        # 如果使用资源池，则在最后需要进行资源交付
        if self.need_resource_pool:
            flows.append(Flow(ticket=self.ticket, flow_type=FlowType.RESOURCE_DELIVERY, flow_alias=_("资源交付")))

        # 判断并添加主机清理节点
        if self.need_recycle:
            flows.append(
                Flow(
                    ticket=self.ticket,
                    flow_type=FlowType.HOST_RECYCLE.value,
                    details=self.recycle_flow_builder(self.ticket).get_params(),
                    flow_alias=_("原主机清理释放"),
                ),
            )

        # 判断并添加资源重导入节点
        if self.need_recycle == PoolType.Resource:
            flows.append(
                Flow(
                    ticket=self.ticket,
                    flow_type=FlowType.HOST_IMPORT_RESOURCE.value,
                    details=self.import_resource_flow_builder(self.ticket).get_params(),
                    flow_alias=_("原主机回收到资源池"),
                ),
            )

        Flow.objects.bulk_create(flows)
        return list(Flow.objects.filter(ticket=self.ticket))

    def transform_alarm_to_ticket_details(self):
        """把监控时间转换为单据详情"""
        pass

    def patch_ticket_detail(self):
        """自定义补充单据详情，留给子类实现"""
        pass

    def alarm_callback_to_ticket_detail(self):
        """告警回调转化为单据详情"""
        pass

    @classmethod
    def _add_itsm_pause_describe(cls, flow_desc, flow_config_map):
        if flow_config_map[cls.ticket_type]["need_itsm"]:
            flow_desc.append(FlowType.get_choice_label(FlowType.BK_ITSM))
        if flow_config_map[cls.ticket_type]["need_manual_confirm"]:
            flow_desc.append(FlowType.get_choice_label(FlowType.PAUSE))
        return flow_desc

    @classmethod
    def describe_ticket_flows(cls, flow_config_map):
        """
        @param flow_config_map: 单据类型与配置的映射
        单据构造类的默认流程描述，固定为：
        单据审批(可选, 默认有) --> 人工确认(可选, 默认有) --> 资源申请(由单据参数判断) ---> inner节点 --> 资源交付(由单据参数判断)
        如果子类覆写了custom_ticket_flows/init_ticket_flows，则同时需要覆写该方法
        """
        need_resource = (cls.resource_apply_builder or cls.resource_batch_apply_builder) is not None
        flow_desc = cls._add_itsm_pause_describe(flow_desc=[], flow_config_map=flow_config_map)
        if need_resource:
            flow_desc.append(FlowType.get_choice_label(FlowType.RESOURCE_APPLY))
        if cls.inner_flow_name:
            flow_desc.append(cls.inner_flow_name)
        if need_resource:
            flow_desc.append(FlowType.get_choice_label(FlowType.RESOURCE_DELIVERY))

        return flow_desc


class BuilderFactory:
    # 单据的注册器类集合
    registry = {}
    # 部署类单据集合
    apply_ticket_type = []
    # 回收类单据集合
    recycle_ticket_type = []
    # 敏感类单据集合
    sensitive_ticket_type = []
    # 单据与集群状态的映射
    ticket_type__cluster_phase = {}
    # 单据和权限动作/资源类型的映射
    ticket_type__iam_action = {}

    @classmethod
    def register(cls, ticket_type: str, **kwargs) -> Callable:
        """
        将单据构造类注册到注册器中
        @param ticket_type: 单据类型
        @param kwargs: 单据注册的额外信息，主要是将单据归为不同的集合中，目前有这几种类型
        1. is_apply: bool ---- 表示单据是否是部署类单据(类似集群的部署，扩容，替换等)
        2. is_recycle: bool ---- 表示单据是否是下架类单据(类似集群的下架，缩容，替换等)
        3. phase: ClusterPhase ---- 表示单据与集群状态的映射
        4. action: ActionMeta ---- 表示单据与权限动作的映射
        5. is_sensitive: bool --- 是否为敏感类单据（有特殊鉴权）
        """

        def inner_wrapper(wrapped_class: TicketFlowBuilder) -> TicketFlowBuilder:
            wrapped_class.ticket_type = ticket_type
            # 若未自定义 flow 流程名称，则使用 单据类型
            if not getattr(wrapped_class, "inner_flow_name", ""):
                setattr(wrapped_class, "inner_flow_name", TicketType.get_choice_label(ticket_type))

            if ticket_type in cls.registry:
                logger.warning(f"Builder [{ticket_type}] already exists. Will replace it")
            cls.registry[ticket_type] = wrapped_class

            if kwargs.get("is_apply") and kwargs.get("is_apply") not in cls.apply_ticket_type:
                cls.apply_ticket_type.append(ticket_type)
            if kwargs.get("is_recycle") and kwargs.get("is_recycle") not in cls.recycle_ticket_type:
                cls.recycle_ticket_type.append(ticket_type)
            if kwargs.get("is_sensitive") and kwargs.get("is_sensitive") not in cls.sensitive_ticket_type:
                cls.sensitive_ticket_type.append(ticket_type)
            if kwargs.get("phase"):
                cls.ticket_type__cluster_phase[ticket_type] = kwargs["phase"]
            if hasattr(ActionEnum, ticket_type) or kwargs.get("iam"):
                # 单据类型和权限动作默认一一对应，如果是特殊指定的则通过iam参数传递
                cls.ticket_type__iam_action[ticket_type] = getattr(ActionEnum, ticket_type, None) or kwargs.get("iam")

            return wrapped_class

        return inner_wrapper

    @classmethod
    def get_builder_cls(cls, ticket_type: str):
        """获取构造器类"""
        if ticket_type not in cls.registry:
            logger.warning(f"Ticket Type: [{ticket_type}] does not exist in the registry")
            raise NotImplementedError

        return cls.registry[ticket_type]

    @classmethod
    def get_serializer(cls, ticket_type: str):
        try:
            return cls.get_builder_cls(ticket_type).serializer()
        except NotImplementedError:
            return serializers.Serializer()

    @classmethod
    def create_builder(cls, ticket: Ticket):
        """创建构造器实例"""
        builder_cls = cls.get_builder_cls(ticket.ticket_type)
        return builder_cls(ticket)


def register_all_builders(path=os.path.dirname(__file__), module_path="backend.ticket.builders"):
    """递归注册当前目录下所有的构建器"""
    for name in os.listdir(path):
        # 忽略无效文件
        if name.endswith(".pyc") or name in ["__init__.py", "__pycache__"]:
            continue

        if os.path.isdir(os.path.join(path, name)):
            register_all_builders(os.path.join(path, name), ".".join([module_path, name]))
        else:
            try:
                module_name = name.replace(".py", "")
                import_path = ".".join([module_path, module_name])
                importlib.import_module(import_path)
            except ModuleNotFoundError as e:
                logger.warning(e)
