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

from typing import List

from backend.configuration.constants import BizSettingsEnum
from backend.db_meta.enums import ClusterType
from backend.iam_app.dataclass import ResourceEnum
from backend.iam_app.dataclass.actions import ActionEnum, ActionMeta
from backend.iam_app.handlers.drf_perm.base import (
    BizDBTypeResourceActionPermission,
    ResourceActionPermission,
    get_request_key_id,
)


class BizDBConfigPermission(BizDBTypeResourceActionPermission):
    """
    业务下数据库配置相关动作鉴权
    """

    def __init__(self, actions: List[ActionMeta] = None):
        self.actions = actions
        super().__init__(
            actions=actions,
            instance_biz_getter=self.instance_biz_getter,
            instance_dbtype_getter=self.instance_dbtype_getter,
        )

    @staticmethod
    def instance_biz_getter(request, view):
        return [get_request_key_id(request, key="bk_biz_id")]

    @staticmethod
    def instance_dbtype_getter(request, view):
        cluster_type = get_request_key_id(request, key="meta_cluster_type")
        return [ClusterType.cluster_type_to_db_type(cluster_type)]


class GlobalConfigPermission(ResourceActionPermission):
    def __init__(self, actions: List[ActionMeta] = None):
        self.actions = actions
        super().__init__(
            actions=actions, resource_meta=ResourceEnum.DBTYPE, instance_ids_getter=self.instance_dbtype_getter
        )

    @staticmethod
    def instance_dbtype_getter(request, view):
        return BizDBConfigPermission.instance_dbtype_getter(request, view)


class BizAssistancePermission(ResourceActionPermission):
    """
    业务单据协作相关鉴权
    """

    def inst_ids_getter(self, request, view):
        data = request.data
        valid_keys = {BizSettingsEnum.BIZ_ASSISTANCE_VARS.value, BizSettingsEnum.BIZ_ASSISTANCE_SWITCH.value}
        try:
            # 检查 data["settings"] 中的任意一个字典的 "key" 是否在 valid_keys 中
            if any(setting["key"] in valid_keys for setting in data.get("settings", [])):
                # 如果有至少一个 key 在 valid_keys 中
                self.actions = [getattr(ActionEnum, "BIZ_ASSISTANCE_VARS_CONFIG")]
            else:
                # 如果所有的 key 都不在 valid_keys 中
                self.actions = []

            self.resource_meta = ResourceEnum.BUSINESS
        except AttributeError:
            raise NotImplementedError

        return [data["bk_biz_id"]]

    def __init__(self):
        super().__init__(actions=None, resource_meta=None, instance_ids_getter=self.inst_ids_getter)
