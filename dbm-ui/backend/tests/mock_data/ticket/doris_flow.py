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

from backend.db_meta.enums.cluster_type import ClusterType
from backend.db_meta.enums.machine_type import MachineType
from backend.db_meta.enums.spec import SpecClusterType
from backend.tests.mock_data import constant
from backend.ticket.constants import TicketType

BK_BIZ_ID = constant.BK_BIZ_ID
DB_MODULE_ID = 1
CLUSTER_ID = 1
BK_USERNAME = "admin"

# doris 上架请求单据
DORIS_APPLY_TICKET_DATA = {
    "ticket_type": TicketType.DORIS_APPLY,
    "bk_biz_id": BK_BIZ_ID,
    "remark": "xxx",
    "details": {
        "ip_source": "resource_pool",
        "query_port": 5001,
        "http_port": 5002,
        "db_version": "2.0.4",
        "cluster_name": "doristest1",
        "cluster_alias": "test1",
        "city_code": "深圳",
        "bk_cloud_id": 0,
        "db_app_abbr": "dba-test",
        "resource_spec": {"follower": {"spec_id": 1, "count": 3}, "observer": {}, "hot": {"spec_id": 3, "count": 2}},
    },
}

# doris启用单据
DORIS_ENABLE_TICKET_DATA = {
    "bk_biz_id": BK_BIZ_ID,
    "remark": "测试启用doris集群",
    "ticket_type": TicketType.DORIS_ENABLE,
    "details": {"cluster_id": CLUSTER_ID},
}

# doris禁用单据
DORIS_DISABLE_TICKET_DATA = {
    "bk_biz_id": BK_BIZ_ID,
    "remark": "测试禁用doris集群",
    "ticket_type": TicketType.DORIS_DISABLE,
    "details": {"cluster_id": CLUSTER_ID + 1},
}

# doris下架单据
DORIS_DESTROY_TICKET_DATA = {
    "bk_biz_id": BK_BIZ_ID,
    "remark": "测试下架doris集群",
    "ticket_type": TicketType.DORIS_DESTROY,
    "details": {"cluster_id": 1},
}

# doris扩容input单据
SCALEUP_INPUT_TICKET_DATA = {
    "bk_biz_id": BK_BIZ_ID,
    "ticket_type": TicketType.DORIS_SCALE_UP,
    "remark": "",
    "details": {
        "cluster_id": CLUSTER_ID,
        "ip_source": "manual_input",
        "nodes": {"observer": [{"ip": "127.0.1.1", "bk_host_id": 101, "bk_cloud_id": 0}]},
    },
}

# doris缩容单据
DORIS_SHRINK_TICKET_DATA = {
    "bk_biz_id": BK_BIZ_ID,
    "ticket_type": TicketType.DORIS_SHRINK,
    "remark": "",
    "details": {
        "cluster_id": CLUSTER_ID,
        "old_nodes": {
            "hot": [],
            "cold": [],
            "observer": [
                {"ip": "127.0.0.5", "bk_host_id": 5, "bk_cloud_id": 0},
                {"ip": "127.0.1.4", "bk_host_id": 4, "bk_cloud_id": 0},
            ],
        },
    },
}

# doris扩容pool单据
SCALEUP_POOL_TICKET_DATA = {
    "bk_biz_id": BK_BIZ_ID,
    "ticket_type": TicketType.DORIS_SCALE_UP,
    "remark": "",
    "details": {
        "cluster_id": CLUSTER_ID,
        "ip_source": "resource_pool",
        "resource_spec": {
            "observer": {"spec_id": 2, "count": 2},
            "hot": {"spec_id": 3, "count": 2},
        },
    },
}

# doris重启单据
DORIS_REBOOT_TICKET_DATA = {
    "bk_biz_id": BK_BIZ_ID,
    "ticket_type": TicketType.DORIS_REBOOT,
    "remark": "xxx",
    "details": {
        "cluster_id": CLUSTER_ID,
        "instance_list": [
            {
                "ip": "127.0.0.1",
                "port": 8030,
                "instance_name": "",
                "bk_host_id": 1,
                "bk_cloud_id": 0,
                "instance_id": 8105,
            },
            {
                "ip": "127.0.0.3",
                "port": 8030,
                "instance_name": "",
                "bk_host_id": 3,
                "bk_cloud_id": 0,
                "instance_id": 8102,
            },
        ],
    },
}

# doris重启单据
DORIS_REPLACE_TICKET_DATA = {
    "bk_biz_id": BK_BIZ_ID,
    "ticket_type": TicketType.DORIS_REPLACE,
    "remark": "",
    "details": {
        "cluster_id": CLUSTER_ID,
        "ip_source": "resource_pool",
        "old_nodes": {
            "hot": [{"ip": "127.0.0.6", "bk_host_id": 2, "bk_cloud_id": 0}],
            "follower": [{"ip": "127.0.0.1", "bk_host_id": 1, "bk_cloud_id": 0}],
            "observer": [{"ip": "127.0.0.4", "bk_host_id": 3, "bk_cloud_id": 0}],
        },
        "resource_spec": {
            "follower": {"spec_id": 1, "count": 1},
            "observer": {"spec_id": 2, "count": 1},
            "hot": {"spec_id": 3, "count": 1},
        },
    },
}

# DORIS 资源申请
DORIS_SOURCE_APPLICATION_DATA = [
    {
        "hot": [
            {
                "bk_biz_id": BK_BIZ_ID,
                "ip": "127.0.0.1",
                "bk_cloud_id": 0,
                "bk_host_id": 1,
                "bk_cpu": 4,
                "bk_disk": 147,
                "bk_mem": 15741,
                "storage_device": {"/data": {"size": 30, "disk_id": "", "disk_type": "ALL", "file_type": ""}},
                "city": "",
                "sub_zone": "",
                "sub_zone_id": "",
                "rack_id": "",
                "device_class": "",
            },
            {
                "bk_biz_id": BK_BIZ_ID,
                "ip": "127.0.0.2",
                "bk_cloud_id": 0,
                "bk_host_id": 2,
                "bk_cpu": 4,
                "bk_disk": 147,
                "bk_mem": 15741,
                "storage_device": {"/data": {"size": 30, "disk_id": "", "disk_type": "ALL", "file_type": ""}},
                "city": "",
                "sub_zone": "",
                "sub_zone_id": "",
                "rack_id": "",
                "device_class": "",
            },
        ],
        "follower": [
            {
                "bk_biz_id": BK_BIZ_ID,
                "ip": "127.0.0.3",
                "bk_cloud_id": 0,
                "bk_host_id": 3,
                "bk_cpu": 8,
                "bk_disk": 98,
                "bk_mem": 31844,
                "storage_device": {"/data": {"size": 30, "disk_id": "", "disk_type": "ALL", "file_type": ""}},
                "city": "",
                "sub_zone": "",
                "sub_zone_id": "",
                "rack_id": "",
                "device_class": "",
            },
            {
                "bk_biz_id": BK_BIZ_ID,
                "ip": "127.0.0.4",
                "bk_cloud_id": 0,
                "bk_host_id": 4,
                "bk_cpu": 8,
                "bk_disk": 98,
                "bk_mem": 31892,
                "storage_device": {"/data": {"size": 30, "disk_id": "", "disk_type": "ALL", "file_type": ""}},
                "city": "",
                "sub_zone": "",
                "sub_zone_id": "",
                "rack_id": "",
                "device_class": "",
            },
            {
                "bk_biz_id": BK_BIZ_ID,
                "ip": "127.0.0.5",
                "bk_cloud_id": 0,
                "bk_host_id": 5,
                "bk_cpu": 4,
                "bk_disk": 147,
                "bk_mem": 15741,
                "storage_device": {"/data": {"size": 30, "disk_id": "", "disk_type": "ALL", "file_type": ""}},
                "city": "",
                "sub_zone": "",
                "sub_zone_id": "",
                "rack_id": "",
                "device_class": "",
            },
        ],
    }
]

# DORIS 规格初始化
DORIS_SPEC_DATA = [
    {
        "spec_id": 1,
        "spec_name": "2核_2G_30G",
        "cpu": {"max": 256, "min": 2},
        "mem": {"max": 256, "min": 2},
        "storage_spec": [{"size": 30, "type": "ALL", "mount_point": "/data"}],
        "spec_cluster_type": SpecClusterType.Doris.value,
        "spec_machine_type": MachineType.DORIS_FOLLOWER.value,
        "device_class": [-1],
        "qps": {"max": 0, "min": 0},
        "enable": 1,
    },
    {
        "spec_id": 2,
        "spec_name": "2核_2G_30G",
        "cpu": {"max": 256, "min": 2},
        "mem": {"max": 256, "min": 2},
        "storage_spec": [{"size": 30, "type": "ALL", "mount_point": "/data"}],
        "spec_cluster_type": SpecClusterType.Doris.value,
        "spec_machine_type": MachineType.DORIS_OBSERVER.value,
        "device_class": [-1],
        "qps": {"max": 0, "min": 0},
        "enable": 1,
    },
    {
        "spec_id": 3,
        "spec_name": "2核_2G_30G",
        "cpu": {"max": 256, "min": 2},
        "mem": {"max": 256, "min": 2},
        "storage_spec": [{"size": 30, "type": "ALL", "mount_point": "/data"}],
        "spec_cluster_type": SpecClusterType.Doris.value,
        "spec_machine_type": MachineType.DORIS_BACKEND.value,
        "device_class": [-1],
        "qps": {"max": 0, "min": 0},
        "enable": 1,
    },
]


# 初始化doris集群
DORIS_CLUSTER_DATA = [
    {
        "id": CLUSTER_ID,
        "creator": BK_USERNAME,
        "updater": BK_USERNAME,
        "name": "doris-test1",
        "alias": "doris-test1",
        "bk_biz_id": BK_BIZ_ID,
        "cluster_type": ClusterType.Doris,
        "db_module_id": 0,
        "immute_domain": "doris.doris01.dba.db",
        "major_version": "2.0.4",
        "phase": "offline",
        "status": "normal",
        "bk_cloud_id": 0,
        "region": "default",
        "time_zone": "+08:00",
        "disaster_tolerance_level": "NONE",
    },
    {
        "id": CLUSTER_ID + 1,
        "creator": BK_USERNAME,
        "updater": BK_USERNAME,
        "name": "doris-test2",
        "alias": "doris-test2",
        "bk_biz_id": BK_BIZ_ID,
        "cluster_type": ClusterType.Doris,
        "db_module_id": 0,
        "immute_domain": "doris.doris02.dba.db",
        "major_version": "2.0.4",
        "phase": "online",
        "status": "normal",
        "bk_cloud_id": 0,
        "region": "default",
        "time_zone": "+08:00",
        "disaster_tolerance_level": "NONE",
    },
]

# DORIS STORAGE实例数据
DORIS_STORAGE_INSTANCE_DATA = [
    {
        "creator": BK_USERNAME,
        "create_at": "2024-03-14 01:36:51.626234",
        "updater": "",
        "update_at": "2024-03-14 01:36:51.626234",
        "version": "2.0.4",
        "port": 8030,
        "db_module_id": DB_MODULE_ID,
        "bk_biz_id": BK_BIZ_ID,
        "access_layer": "storage",
        "machine_type": MachineType.DORIS_FOLLOWER.value,
        "cluster_type": ClusterType.Doris.value,
        "status": "running",
        "name": "",
        "time_zone": "+08:00",
        "bk_instance_id": 7089,
        "machine_id": 1,
        "phase": "online",
        "instance_role": "doris_follower",
        "instance_inner_role": "orphan",
    },
    {
        "creator": BK_USERNAME,
        "create_at": "2024-03-14 01:36:51.626234",
        "updater": "",
        "update_at": "2024-03-14 01:36:51.626234",
        "version": "2.0.4",
        "port": 8030,
        "db_module_id": DB_MODULE_ID,
        "bk_biz_id": BK_BIZ_ID,
        "access_layer": "storage",
        "machine_type": MachineType.DORIS_FOLLOWER.value,
        "cluster_type": ClusterType.Doris.value,
        "status": "running",
        "name": "",
        "time_zone": "+08:00",
        "bk_instance_id": 7089,
        "machine_id": 2,
        "phase": "online",
        "instance_role": "doris_follower",
        "instance_inner_role": "orphan",
    },
    {
        "creator": BK_USERNAME,
        "create_at": "2024-03-14 01:36:51.626234",
        "updater": "",
        "update_at": "2024-03-14 01:36:51.626234",
        "version": "2.0.4",
        "port": 8030,
        "db_module_id": DB_MODULE_ID,
        "bk_biz_id": BK_BIZ_ID,
        "access_layer": "storage",
        "machine_type": MachineType.DORIS_FOLLOWER.value,
        "cluster_type": ClusterType.Doris.value,
        "status": "running",
        "name": "",
        "time_zone": "+08:00",
        "bk_instance_id": 7089,
        "machine_id": 3,
        "phase": "online",
        "instance_role": "doris_follower",
        "instance_inner_role": "orphan",
    },
    {
        "creator": BK_USERNAME,
        "create_at": "2024-03-14 01:36:51.626234",
        "updater": "",
        "update_at": "2024-03-14 01:36:51.626234",
        "version": "2.0.4",
        "port": 8030,
        "db_module_id": DB_MODULE_ID,
        "bk_biz_id": BK_BIZ_ID,
        "access_layer": "storage",
        "machine_type": MachineType.DORIS_FOLLOWER.value,
        "cluster_type": ClusterType.Doris.value,
        "status": "running",
        "name": "",
        "time_zone": "+08:00",
        "bk_instance_id": 7089,
        "machine_id": 4,
        "phase": "online",
        "instance_role": "doris_observer",
        "instance_inner_role": "orphan",
    },
    {
        "creator": BK_USERNAME,
        "create_at": "2024-03-14 01:36:51.626234",
        "updater": "",
        "update_at": "2024-03-14 01:36:51.626234",
        "version": "2.0.4",
        "port": 8030,
        "db_module_id": DB_MODULE_ID,
        "bk_biz_id": BK_BIZ_ID,
        "access_layer": "storage",
        "machine_type": MachineType.DORIS_FOLLOWER.value,
        "cluster_type": ClusterType.Doris.value,
        "status": "running",
        "name": "",
        "time_zone": "+08:00",
        "bk_instance_id": 7089,
        "machine_id": 5,
        "phase": "online",
        "instance_role": "doris_observer",
        "instance_inner_role": "orphan",
    },
    {
        "creator": BK_USERNAME,
        "create_at": "2024-03-14 01:36:51.626234",
        "updater": "",
        "update_at": "2024-03-14 01:36:51.626234",
        "version": "2.0.4",
        "port": 8040,
        "db_module_id": DB_MODULE_ID,
        "bk_biz_id": BK_BIZ_ID,
        "access_layer": "storage",
        "machine_type": MachineType.DORIS_FOLLOWER.value,
        "cluster_type": ClusterType.Doris.value,
        "status": "running",
        "name": "",
        "time_zone": "+08:00",
        "bk_instance_id": 7089,
        "machine_id": 6,
        "phase": "online",
        "instance_role": "doris_backend_hot",
        "instance_inner_role": "orphan",
    },
    {
        "creator": BK_USERNAME,
        "create_at": "2024-03-14 01:36:51.626234",
        "updater": "",
        "update_at": "2024-03-14 01:36:51.626234",
        "version": "2.0.4",
        "port": 8040,
        "db_module_id": DB_MODULE_ID,
        "bk_biz_id": BK_BIZ_ID,
        "access_layer": "storage",
        "machine_type": MachineType.DORIS_FOLLOWER.value,
        "cluster_type": ClusterType.Doris.value,
        "status": "running",
        "name": "",
        "time_zone": "+08:00",
        "bk_instance_id": 7089,
        "machine_id": 7,
        "phase": "online",
        "instance_role": "doris_backend_hot",
        "instance_inner_role": "orphan",
    },
]

# DORIS 集群机器信息
DORIS_MACHINE_DATA = [
    {
        "creator": BK_USERNAME,
        "create_at": "2024-03-13 11:14:48.433116",
        "updater": "",
        "update_at": "2024-03-13 11:14:48.433116",
        "ip": "127.0.0.1",
        "bk_biz_id": BK_BIZ_ID,
        "db_module_id": 0,
        "access_layer": "storage",
        "machine_type": MachineType.DORIS_FOLLOWER.value,
        "cluster_type": ClusterType.Doris.value,
        "bk_host_id": 1,
        "bk_os_name": "linux centos",
        "bk_idc_area": "",
        "bk_idc_area_id": 0,
        "bk_sub_zone": "",
        "bk_sub_zone_id": 0,
        "bk_rack": "",
        "bk_rack_id": 0,
        "bk_svr_device_cls_name": "",
        "bk_idc_name": "",
        "bk_idc_id": 0,
        "bk_cloud_id": 0,
        "net_device_id": "",
        "bk_city_id": 0,
        "spec_config": '{"id": 1, "cpu": {"max": 64, "min": 2}, "mem": {"max": 64, "min": 4}, '
        '"qps": {"max": 0, "min": 0}, "name": "1核_4G_20G", "count": 1, "device_class": [], '
        '"storage_spec": [{"size": 10, "type": "ALL", "mount_point": "/data"}]}',
        "spec_id": 1,
        "bk_agent_id": "",
    },
    {
        "creator": BK_USERNAME,
        "create_at": "2024-03-13 11:14:48.433116",
        "updater": "",
        "update_at": "2024-03-13 11:14:48.433116",
        "ip": "127.0.0.2",
        "bk_biz_id": BK_BIZ_ID,
        "db_module_id": 0,
        "access_layer": "storage",
        "machine_type": MachineType.DORIS_FOLLOWER.value,
        "cluster_type": ClusterType.Doris.value,
        "bk_host_id": 2,
        "bk_os_name": "linux centos",
        "bk_idc_area": "",
        "bk_idc_area_id": 0,
        "bk_sub_zone": "",
        "bk_sub_zone_id": 0,
        "bk_rack": "",
        "bk_rack_id": 0,
        "bk_svr_device_cls_name": "",
        "bk_idc_name": "",
        "bk_idc_id": 0,
        "bk_cloud_id": 0,
        "net_device_id": "",
        "bk_city_id": 0,
        "spec_config": '{"id": 1, "cpu": {"max": 64, "min": 2}, "mem": {"max": 64, "min": 4}, '
        '"qps": {"max": 0, "min": 0}, "name": "1核_4G_20G", "count": 1, "device_class": [], '
        '"storage_spec": [{"size": 10, "type": "ALL", "mount_point": "/data"}]}',
        "spec_id": 1,
        "bk_agent_id": "",
    },
    {
        "creator": BK_USERNAME,
        "create_at": "2024-03-13 11:14:48.433116",
        "updater": "",
        "update_at": "2024-03-13 11:14:48.433116",
        "ip": "127.0.0.3",
        "bk_biz_id": BK_BIZ_ID,
        "db_module_id": 0,
        "access_layer": "storage",
        "machine_type": MachineType.DORIS_FOLLOWER.value,
        "cluster_type": ClusterType.Doris.value,
        "bk_host_id": 3,
        "bk_os_name": "linux centos",
        "bk_idc_area": "",
        "bk_idc_area_id": 0,
        "bk_sub_zone": "",
        "bk_sub_zone_id": 0,
        "bk_rack": "",
        "bk_rack_id": 0,
        "bk_svr_device_cls_name": "",
        "bk_idc_name": "",
        "bk_idc_id": 0,
        "bk_cloud_id": 0,
        "net_device_id": "",
        "bk_city_id": 0,
        "spec_config": '{"id": 1, "cpu": {"max": 64, "min": 2}, "mem": {"max": 64, "min": 4}, '
        '"qps": {"max": 0, "min": 0}, "name": "1核_4G_20G", "count": 1, "device_class": [], '
        '"storage_spec": [{"size": 10, "type": "ALL", "mount_point": "/data"}]}',
        "spec_id": 1,
        "bk_agent_id": "",
    },
    {
        "creator": BK_USERNAME,
        "create_at": "2024-03-13 11:14:48.433116",
        "updater": "",
        "update_at": "2024-03-13 11:14:48.433116",
        "ip": "127.0.0.4",
        "bk_biz_id": BK_BIZ_ID,
        "db_module_id": 0,
        "access_layer": "storage",
        "machine_type": MachineType.DORIS_OBSERVER.value,
        "cluster_type": ClusterType.Doris.value,
        "bk_host_id": 4,
        "bk_os_name": "linux centos",
        "bk_idc_area": "",
        "bk_idc_area_id": 0,
        "bk_sub_zone": "",
        "bk_sub_zone_id": 0,
        "bk_rack": "",
        "bk_rack_id": 0,
        "bk_svr_device_cls_name": "",
        "bk_idc_name": "",
        "bk_idc_id": 0,
        "bk_cloud_id": 0,
        "net_device_id": "",
        "bk_city_id": 0,
        "spec_config": '{"id": 2, "cpu": {"max": 64, "min": 2}, "mem": {"max": 64, "min": 4}, '
        '"qps": {"max": 0, "min": 0}, "name": "1核_4G_20G", "count": 1, "device_class": [], '
        '"storage_spec": [{"size": 10, "type": "ALL", "mount_point": "/data"}]}',
        "spec_id": 2,
        "bk_agent_id": "",
    },
    {
        "creator": BK_USERNAME,
        "create_at": "2024-03-13 11:14:48.433116",
        "updater": "",
        "update_at": "2024-03-13 11:14:48.433116",
        "ip": "127.0.0.5",
        "bk_biz_id": BK_BIZ_ID,
        "db_module_id": 0,
        "access_layer": "storage",
        "machine_type": MachineType.DORIS_OBSERVER.value,
        "cluster_type": ClusterType.Doris.value,
        "bk_host_id": 5,
        "bk_os_name": "linux centos",
        "bk_idc_area": "",
        "bk_idc_area_id": 0,
        "bk_sub_zone": "",
        "bk_sub_zone_id": 0,
        "bk_rack": "",
        "bk_rack_id": 0,
        "bk_svr_device_cls_name": "",
        "bk_idc_name": "",
        "bk_idc_id": 0,
        "bk_cloud_id": 0,
        "net_device_id": "",
        "bk_city_id": 0,
        "spec_config": '{"id": 2, "cpu": {"max": 64, "min": 2}, "mem": {"max": 64, "min": 4}, '
        '"qps": {"max": 0, "min": 0}, "name": "1核_4G_20G", "count": 1, "device_class": [], '
        '"storage_spec": [{"size": 10, "type": "ALL", "mount_point": "/data"}]}',
        "spec_id": 2,
        "bk_agent_id": "",
    },
    {
        "creator": BK_USERNAME,
        "create_at": "2024-03-13 11:14:48.433116",
        "updater": "",
        "update_at": "2024-03-13 11:14:48.433116",
        "ip": "127.0.0.6",
        "bk_biz_id": BK_BIZ_ID,
        "db_module_id": 0,
        "access_layer": "storage",
        "machine_type": MachineType.DORIS_BACKEND.value,
        "cluster_type": ClusterType.Doris.value,
        "bk_host_id": 6,
        "bk_os_name": "linux centos",
        "bk_idc_area": "",
        "bk_idc_area_id": 0,
        "bk_sub_zone": "",
        "bk_sub_zone_id": 0,
        "bk_rack": "",
        "bk_rack_id": 0,
        "bk_svr_device_cls_name": "",
        "bk_idc_name": "",
        "bk_idc_id": 0,
        "bk_cloud_id": 0,
        "net_device_id": "",
        "bk_city_id": 0,
        "spec_config": '{"id": 3, "cpu": {"max": 64, "min": 2}, "mem": {"max": 64, "min": 4}, '
        '"qps": {"max": 0, "min": 0}, "name": "1核_4G_20G", "count": 1, "device_class": [], '
        '"storage_spec": [{"size": 10, "type": "ALL", "mount_point": "/data"}]}',
        "spec_id": 3,
        "bk_agent_id": "",
    },
    {
        "creator": BK_USERNAME,
        "create_at": "2024-03-13 11:14:48.433116",
        "updater": "",
        "update_at": "2024-03-13 11:14:48.433116",
        "ip": "127.0.0.7",
        "bk_biz_id": BK_BIZ_ID,
        "db_module_id": 0,
        "access_layer": "storage",
        "machine_type": MachineType.DORIS_BACKEND.value,
        "cluster_type": ClusterType.Doris.value,
        "bk_host_id": 7,
        "bk_os_name": "linux centos",
        "bk_idc_area": "",
        "bk_idc_area_id": 0,
        "bk_sub_zone": "",
        "bk_sub_zone_id": 0,
        "bk_rack": "",
        "bk_rack_id": 0,
        "bk_svr_device_cls_name": "",
        "bk_idc_name": "",
        "bk_idc_id": 0,
        "bk_cloud_id": 0,
        "net_device_id": "",
        "bk_city_id": 0,
        "spec_config": '{"id": 3, "cpu": {"max": 64, "min": 2}, "mem": {"max": 64, "min": 4}, '
        '"qps": {"max": 0, "min": 0}, "name": "1核_4G_20G", "count": 1, "device_class": [], '
        '"storage_spec": [{"size": 10, "type": "ALL", "mount_point": "/data"}]}',
        "spec_id": 3,
        "bk_agent_id": "",
    },
]
