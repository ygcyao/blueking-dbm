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
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Union

from django.utils.translation import gettext as _

from backend.components.dbresource.client import DBResourceApi
from backend.configuration.constants import AffinityEnum
from backend.configuration.models import DBAdministrator
from backend.core import notify
from backend.db_meta.models import Spec
from backend.db_services.dbresource.exceptions import ResourceApplyException, ResourceApplyInsufficientException
from backend.ticket import constants
from backend.ticket.constants import FlowCallbackType, FlowType, ResourceApplyErrCode, TodoType
from backend.ticket.flow_manager.base import BaseTicketFlow
from backend.ticket.flow_manager.delivery import DeliveryFlow
from backend.ticket.models import Flow, Todo
from backend.utils.basic import generate_root_id
from backend.utils.time import datetime2str

logger = logging.getLogger("root")

HOST_IN_USE = "host_in_use"


class ResourceApplyFlow(BaseTicketFlow):
    """
    内置资源申请流程
    """

    def __init__(self, flow_obj: Flow):
        super().__init__(flow_obj=flow_obj)
        self.resource_apply_status = flow_obj.details.get("resource_apply_status", None)
        self.allow_resource_empty = flow_obj.details.get("allow_resource_empty", False)

    @property
    def _start_time(self) -> str:
        return datetime2str(self.flow_obj.create_at)

    @property
    def _end_time(self) -> Optional[str]:
        return datetime2str(self.flow_obj.update_at)

    @property
    def _summary(self) -> str:
        return _("资源申请状态{status_display}").format(
            status_display=constants.TicketFlowStatus.get_choice_label(self.status)
        )

    @property
    def status(self) -> str:
        # 覆写base的状态判断，资源池申请节点的状态判断逻辑不同
        return self._status

    def update_flow_status(self, status):
        self.flow_obj.update_status(status)
        return status

    @property
    def _status(self) -> str:
        # 任务流程未创建时未PENDING状态
        if not self.flow_obj.flow_obj_id:
            return self.update_flow_status(constants.TicketFlowStatus.PENDING)

        # 如果资源申请成功，则直接返回success
        if self.resource_apply_status:
            return self.update_flow_status(constants.TicketFlowStatus.SUCCEEDED)

        if self.flow_obj.err_msg:
            # 如果是其他情况引起的错误，则直接返回fail
            if not self.flow_obj.todo_of_flow.exists():
                return self.update_flow_status(constants.TicketFlowStatus.FAILED)
            # 如果是资源申请的todo状态，则判断todo是否完成
            if self.ticket.todo_of_ticket.exist_unfinished():
                return self.update_flow_status(constants.TicketFlowStatus.RUNNING)
            else:
                return self.flow_obj.status

        # 其他情况认为还在RUNNING状态
        return self.update_flow_status(constants.TicketFlowStatus.RUNNING)

    @property
    def _url(self) -> str:
        return ""

    def callback(self) -> None:
        """
        resource节点独有的钩子函数，执行后继流程节点动作，约定为后继节点的finner flow填充参数
        默认是调用ParamBuilder的后继方法
        """
        callback_info = self.flow_obj.details["callback_info"]
        callback_module = importlib.import_module(callback_info[f"{FlowCallbackType.POST_CALLBACK}_callback_module"])
        callback_class = getattr(callback_module, callback_info[f"{FlowCallbackType.POST_CALLBACK}_callback_class"])
        getattr(callback_class(self.ticket), f"{FlowCallbackType.POST_CALLBACK}_callback")()

    def run(self):
        """执行流程并记录流程对象ID"""
        resource_flow_id = generate_root_id()
        self.run_status_handler(resource_flow_id)

        try:
            self._run()
        except ResourceApplyInsufficientException as err:
            # 如果是补货失败，则只更新错误信息，认为单据和flow都在运行中
            self.flow_obj.err_msg = err.message
            self.flow_obj.save(update_fields=["err_msg", "update_at"])
        except Exception as err:  # pylint: disable=broad-except
            self.run_error_status_handler(err)

    def _format_resource_hosts(self, hosts):
        """格式化申请的主机参数"""
        return [
            {
                # 没有业务ID，认为是公共资源
                "bk_biz_id": host.get("bk_biz_id", 0),
                "ip": host["ip"],
                "bk_cloud_id": host["bk_cloud_id"],
                "bk_host_id": host["bk_host_id"],
                # 补充机器的内存，cpu和磁盘信息。(bk_disk的单位是GB, bk_mem的单位是MB)
                "bk_cpu": host["cpu_num"],
                "bk_disk": host["total_storage_cap"],
                "bk_mem": host["dram_cap"],
                # bk_disk为系统盘，storage_device为数据盘/data|/data1
                "storage_device": host["storage_device"],
                # 补充城市和园区
                "city": host.get("city"),
                "sub_zone": host.get("sub_zone"),
                "sub_zone_id": host.get("sub_zone_id"),
                "rack_id": host.get("rack_id"),
                "device_class": host.get("device_class"),
            }
            for host in hosts
        ]

    def apply_resource(self, ticket_data):
        """资源申请"""
        apply_params: Dict[str, Union[str, Any]] = {
            "for_biz_id": ticket_data["bk_biz_id"],
            "resource_type": self.ticket.group,
            "bill_id": str(self.ticket.id),
            "bill_type": self.ticket.ticket_type,
            # 消费情况下的task id为inner flow
            "task_id": self.ticket.next_flow().flow_obj_id,
            "operator": self.ticket.creator,
            "details": self.fetch_apply_params(ticket_data),
        }

        # 如果无资源申请，则返回空
        if not apply_params["details"]:
            return "", {}

        # groups_in_same_location只在同城同园区亲和性下才成效，保证所有组申请的机器都在同园区
        # 目前所有组亲和性相同，任取一个判断即可
        affinity = apply_params["details"][0]["affinity"]
        if affinity in [AffinityEnum.SAME_SUBZONE, AffinityEnum.SAME_SUBZONE_CROSS_SWTICH]:
            apply_params.update(groups_in_same_location=True)

        # 向资源池申请机器
        resp = DBResourceApi.resource_pre_apply(params=apply_params, raw=True)
        if resp["code"] == ResourceApplyErrCode.RESOURCE_LAKE:
            # 如果是资源不足，则创建补货单，用户手动处理后可以重试资源申请
            self.create_replenish_todo()
            raise ResourceApplyInsufficientException(_("资源不足申请失败，请前往补货后重试{}").format(resp.get("message")))
        elif resp["code"] in ResourceApplyErrCode.get_values():
            raise ResourceApplyException(
                _("资源池服务出现系统错误，请联系管理员或稍后重试。错误信息: [{}]{}").format(
                    ResourceApplyErrCode.get_choice_label(resp["code"]), resp.get("message")
                )
            )
        elif resp["code"] != 0:
            raise ResourceApplyException(
                _("资源池相关服务出现未知异常，请联系管理员处理。错误信息: [{}]{}").format(resp["code"], resp.get("message"))
            )

        # 将资源池申请的主机信息转换为单据参数
        resource_request_id, apply_data = resp["request_id"], resp["data"]
        node_infos: Dict[str, List] = defaultdict(list)
        for info in apply_data:
            role = info["item"]
            host_infos = self._format_resource_hosts(info["data"])
            # 如果是部署方案的分组，则用backend_group包裹。里面每一小组是一对master/slave;
            # 否则就按角色分组填入
            group_name = role.rsplit("_", 1)[0]
            if "backend_group" in role:
                node_infos[group_name].append({"master": host_infos[0], "slave": host_infos[1]})
            else:
                node_infos[group_name].extend(host_infos)

        return resource_request_id, node_infos

    def create_replenish_todo(self):
        """创建补货单"""
        if Todo.objects.filter(flow=self.flow_obj, ticket=self.ticket, type=TodoType.RESOURCE_REPLENISH).exists():
            return

        from backend.ticket.todos.pause_todo import ResourceReplenishTodoContext

        dba = DBAdministrator.get_biz_db_type_admins(self.ticket.bk_biz_id, self.ticket.group)
        Todo.objects.create(
            name=_("【{}】流程所需资源不足").format(self.ticket.get_ticket_type_display()),
            flow=self.flow_obj,
            ticket=self.ticket,
            type=TodoType.RESOURCE_REPLENISH,
            context=ResourceReplenishTodoContext(
                flow_id=self.flow_obj.id, ticket_id=self.ticket.id, user=self.ticket.creator, administrators=dba
            ).to_dict(),
        )
        notify.send_msg.apply_async(args=(self.ticket.id,))

    def fetch_apply_params(self, ticket_data):
        """
        构造资源申请参数, ticket_data主要包含两项信息：
        resource_spec: 资源申请的规格信息
        resource_params: 资源申请的额外过滤信息, 主要用于拓展资源申请的维度(比如操作系统，网卡等等)
        """
        bk_cloud_id: int = ticket_data["bk_cloud_id"]
        details: List[Dict[str, Any]] = []

        # 根据规格来填充相应机器的申请参数
        resource_spec = ticket_data["resource_spec"]
        for role, role_spec in resource_spec.items():
            # 如果申请数量为0/规格ID不合法(存在spec id为0 --> 是前端表单的默认值)，则跳过
            if not role_spec["count"] or not role_spec["spec_id"]:
                continue
            # 填充规格申请参数
            if role == "backend_group":
                count, group_count = int(role_spec["count"]) * 2, 2
            else:
                count, group_count = int(role_spec["count"]), int(role_spec.get("group_count", role_spec["count"]))
            details.extend(
                Spec.objects.get(spec_id=role_spec["spec_id"]).get_group_apply_params(
                    group_mark=role,
                    count=count,
                    bk_cloud_id=bk_cloud_id,
                    group_count=group_count,
                    affinity=role_spec.get("affinity", AffinityEnum.NONE.value),
                    location_spec=role_spec.get("location_spec"),
                )
            )

        # 如果允许跳过资源申请，则返回空，否则报错
        if not details and self.allow_resource_empty:
            return []
        elif not details and not self.allow_resource_empty:
            raise ResourceApplyException(_("申请的资源总数为0，资源申请不合法"))

        # 如果有额外的过滤条件，则补充到每个申请group的details中
        if ticket_data.get("resource_params"):
            resource_params = ticket_data["resource_params"]
            details = [{**detail, **resource_params} for detail in details]

        return details

    def patch_resource_spec(self, ticket_data, spec_map: Dict[int, Spec] = None):
        """
        将资源池部署信息写入到ticket_data。
        @param ticket_data: 待填充的字典
        @param spec_map: 规格缓存数据, 避免频繁查询数据库
        """

        spec_map = spec_map or {}
        resource_spec = ticket_data["resource_spec"]
        for role, role_spec in copy.deepcopy(resource_spec).items():
            # 如果该存在无需申请，则跳过
            if not role_spec["count"] or not role_spec["spec_id"]:
                continue

            spec = spec_map.get(role_spec["spec_id"]) or Spec.objects.get(spec_id=role_spec["spec_id"])
            role_info = {**spec.get_spec_info(), "count": role_spec["count"]}
            # 如果角色是backend_group，则默认角色信息写入master和slave
            if role == "backend_group":
                resource_spec["master"] = resource_spec["slave"] = role_info
            else:
                resource_spec[role] = role_info

    def write_node_infos(self, ticket_data, node_infos):
        """将资源申请信息写入ticket_data"""
        ticket_data.update({"nodes": node_infos})

    def _run(self) -> None:
        next_flow = self.ticket.next_flow()
        if next_flow.flow_type != FlowType.INNER_FLOW:
            raise ResourceApplyException(_("资源申请下一个节点不为部署节点，请重新编排"))

        # 提前为inner flow生成root id，要写入操作记录中
        next_flow.flow_obj_id = generate_root_id()
        next_flow.save()

        # 资源申请
        resource_request_id, node_infos = self.apply_resource(self.flow_obj.details)

        # 将机器信息写入ticket和inner flow
        self.write_node_infos(next_flow.details["ticket_data"], node_infos)
        self.patch_resource_spec(next_flow.details["ticket_data"])
        next_flow.save(update_fields=["details"])
        # 相关信息回填到单据和resource flow中
        self.ticket.update_details(resource_request_id=resource_request_id, nodes=node_infos)
        self.flow_obj.update_details(resource_apply_status=True)

        # 调用后继函数
        self.callback()

        # 执行下一个流程
        from backend.ticket.flow_manager.manager import TicketFlowManager

        TicketFlowManager(ticket=self.ticket).run_next_flow()


class ResourceBatchApplyFlow(ResourceApplyFlow):
    """
    内置批量的资源申请，一般单据的批量操作。(比如mysql的添加从库)
    内置格式参考：
    "info": [
        {
            "cluster_id": [1, 2, 3, ...],
            "resource_spec": {
                "new_slave": {"spec_id"": 1, "count": 2}
            }
        }
    ]
    """

    def patch_resource_spec(self, ticket_data):
        spec_ids: List[int] = []
        for info in ticket_data["infos"]:
            spec_ids.extend([data["spec_id"] for data in info["resource_spec"].values()])

        # 提前缓存数据库查询数据，避免多次IO
        spec_map = {spec.spec_id: spec for spec in Spec.objects.filter(spec_id__in=spec_ids)}
        for info in ticket_data["infos"]:
            super().patch_resource_spec(info, spec_map)

    def write_node_infos(self, ticket_data, node_infos):
        """
        解析每个角色前缀，并将角色申请资源填充到对应的info中
        """
        for node_group, nodes in node_infos.items():
            # 获取当前角色组在原来info的位置，并填充申请的资源信息
            index, group = node_group.split("_", 1)
            ticket_data["infos"][int(index)][group] = nodes

    def fetch_apply_params(self, ticket_data):
        """
        将每个info中需要申请的角色加上前缀index，
        并且填充为统一的apply_details进行申请
        """
        apply_details: List[Dict[str, Any]] = []
        for index, info in enumerate(ticket_data["infos"]):
            details = super().fetch_apply_params(info)
            # 为申请的角色组表示序号
            for node_params in details:
                node_params["group_mark"] = f"{index}_{node_params['group_mark']}"

            apply_details.extend(details)

        return apply_details


class ResourceDeliveryFlow(DeliveryFlow):
    """
    内置资源申请交付流程，主要是通知资源池机器使用成功
    """

    def confirm_resource(self, ticket_data):
        # 获取request_id和host_ids，资源池后台会校验这两个值是否合法
        resource_request_id: str = ticket_data["resource_request_id"]
        nodes: Dict[str, List] = ticket_data.get("nodes")
        host_ids: List[int] = []

        # 无资源确认，跳过
        if not nodes:
            return

        # 统计资源确认的主机ID
        for role, role_info in nodes.items():
            # 批量后台申请的角色为: {index}_backend_group
            if "backend_group" in role:
                host_ids.extend([host["bk_host_id"] for backend in role_info for host in backend.values()])
            else:
                host_ids.extend([host["bk_host_id"] for host in role_info])

        # 确认资源申请
        DBResourceApi.resource_confirm(params={"request_id": resource_request_id, "host_ids": host_ids})

    def _run(self) -> str:
        self.confirm_resource(self.ticket.details)
        return super()._run()


class ResourceBatchDeliveryFlow(ResourceDeliveryFlow):
    """
    内置资源申请批量交付流程，主要是通知资源池机器使用成功
    """

    def _run(self) -> str:
        # 暂时与单独交付节点没有区别
        return super()._run()
