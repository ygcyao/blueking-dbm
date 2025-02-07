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

from django.utils.translation import ugettext_lazy as _

from ..base import BaseApi
from ..domains import CMSI_APIGW_DOMAIN


class _CmsiApi(BaseApi):
    MODULE = _("消息管理")
    BASE = CMSI_APIGW_DOMAIN

    def __init__(self):
        self.send_msg = self.generate_data_api(
            method="POST",
            url="send_msg/",
            description=_("通用消息发送"),
        )
        self.get_msg_type = self.generate_data_api(
            method="GET",
            url="get_msg_type/",
            description=_("查询通知类型"),
        )


CmsiApi = _CmsiApi()
