/*
 * TencentBlueKing is pleased to support the open source community by making 蓝鲸智云-DB管理系统(BlueKing-BK-DBM) available.
 *
 * Copyright (C) 2017-2023 THL A29 Limited; a Tencent company. All rights reserved.
 *
 * Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at https://opensource.org/licenses/MIT
 *
 * Unless required by applicable law or agreed to in writing; software distributed under the License is distributed
 * on an "AS IS" BASIS; WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND; either express or implied. See the License for
 * the specific language governing permissions and limitations under the License.
 */

import type { HostInfo, InstanceListSpecConfig, InstanceRelatedCluster } from '@services/types';

import { type ClusterInstStatus, clusterInstStatus } from '@common/const';

import { isRecentDays, utcDisplayTime } from '@utils';

export default class RedisInstance {
  bk_cloud_id: number;
  bk_cloud_name: string;
  bk_cpu: number;
  bk_disk: number;
  bk_host_id: number;
  bk_mem: number;
  db_version: string;
  bk_sub_zone: string;
  cluster_id: number;
  cluster_name: string;
  cluster_type: string;
  create_at: string;
  db_module_id: number;
  host_info: HostInfo;
  id: number;
  instance_address: string;
  ip: string;
  master_domain: string;
  permission: {
    redis_view: boolean;
  };
  port: number;
  related_clusters: InstanceRelatedCluster[];
  role: string;
  slave_domain: string;
  spce_config: InstanceListSpecConfig;
  status: ClusterInstStatus;
  version: string;

  constructor(payload = {} as RedisInstance) {
    this.bk_cloud_id = payload.bk_cloud_id || 0;
    this.bk_cloud_name = payload.bk_cloud_name || '';
    this.bk_cpu = payload.bk_cpu || 0;
    this.bk_disk = payload.bk_disk || 0;
    this.bk_host_id = payload.bk_host_id || 0;
    this.bk_mem = payload.bk_mem || 0;
    this.bk_sub_zone = payload.bk_sub_zone || '';
    this.cluster_id = payload.cluster_id || 0;
    this.cluster_name = payload.cluster_name || '';
    this.cluster_type = payload.cluster_type || '';
    this.create_at = payload.create_at || '';
    this.db_module_id = payload.db_module_id || 0;
    this.db_version = payload.db_version || '';
    this.host_info = payload.host_info || {};
    this.id = payload.id || 0;
    this.instance_address = payload.instance_address || '';
    this.ip = payload.ip || '';
    this.master_domain = payload.master_domain || '';
    this.permission = payload.permission || {};
    this.port = payload.port || 0;
    this.related_clusters = payload.related_clusters || [];
    this.role = payload.role || '';
    this.slave_domain = payload.slave_domain || '';
    this.spce_config = payload.spce_config || {};
    this.status = payload.status || '';
    this.version = payload.version || '';
  }

  get createAtDisplay() {
    return utcDisplayTime(this.create_at);
  }

  get isNew() {
    return isRecentDays(this.create_at, 24 * 3);
  }

  get getStatusInfo() {
    return clusterInstStatus[this.status] || clusterInstStatus.unavailable;
  }
}
