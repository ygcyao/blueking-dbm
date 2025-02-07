/*
 * TencentBlueKing is pleased to support the open source community by making 蓝鲸智云-DB管理系统(BlueKing-BK-DBM) available.
 *
 * Copyright (C) 2017-2023 THL A29 Limited, a Tencent company. All rights reserved.
 *
 * Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at https://opensource.org/licenses/MIT
 *
 * Unless required by applicable law or agreed to in writing, software distributed under the License is distributed
 * on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for
 * the specific language governing permissions and limitations under the License.
 */

import { uniq } from 'lodash';

import type { ClusterListEntry, ClusterListNode, ClusterListOperation, ClusterListSpec } from '@services/types';

import { ClusterAffinityMap, ClusterTypes, TicketTypes } from '@common/const';

import { t } from '@locales/index';

import ClusterBase from '../_clusterBase';

const STATUS_NORMAL = 'normal';
const STATUS_ABNORMAL = 'abnormal';

export default class Doris extends ClusterBase {
  static STATUS_NORMAL = STATUS_NORMAL;
  static STATUS_ABNORMAL = STATUS_ABNORMAL;

  static DORIS_ENABLE = TicketTypes.DORIS_ENABLE;
  static DORIS_DISABLE = TicketTypes.DORIS_DISABLE;
  static DORIS_DESTROY = TicketTypes.DORIS_DESTROY;
  static DORIS_SCALE_UP = TicketTypes.DORIS_SCALE_UP;
  static DORIS_SHRINK = TicketTypes.DORIS_SHRINK;
  static DORIS_REPLACE = TicketTypes.DORIS_REPLACE;
  static DORIS_REBOOT = TicketTypes.DORIS_REBOOT;

  static operationIconMap = {
    [Doris.DORIS_ENABLE]: t('启用中'),
    [Doris.DORIS_DISABLE]: t('禁用中'),
    [Doris.DORIS_DESTROY]: t('删除中'),
    [Doris.DORIS_SCALE_UP]: t('扩容中'),
    [Doris.DORIS_SHRINK]: t('缩容中'),
    [Doris.DORIS_REPLACE]: t('替换中'),
    [Doris.DORIS_REBOOT]: t('重启中'),
  };

  static operationTextMap = {
    [Doris.DORIS_ENABLE]: t('启用任务进行中'),
    [Doris.DORIS_DISABLE]: t('禁用任务进行中'),
    [Doris.DORIS_DESTROY]: t('删除任务进行中'),
    [Doris.DORIS_SCALE_UP]: t('扩容任务进行中'),
    [Doris.DORIS_SHRINK]: t('缩容任务进行中'),
    [Doris.DORIS_REPLACE]: t('替换任务进行中'),
    [Doris.DORIS_REBOOT]: t('实例重启任务进行中'),
  };

  access_url: string;
  bk_biz_id: number;
  bk_biz_name: number;
  bk_cloud_id: number;
  bk_cloud_name: string;
  bk_sub_zone: string;
  cluster_access_port: number;
  cluster_alias: string;
  cluster_entry: ClusterListEntry[];
  cluster_name: string;
  cluster_spec: ClusterListSpec;
  cluster_stats: Record<'used' | 'total' | 'in_use', number>;
  cluster_time_zone: string;
  cluster_type: ClusterTypes;
  cluster_type_name: string;
  create_at: string;
  creator: string;
  disaster_tolerance_level: keyof typeof ClusterAffinityMap;
  domain: string;
  doris_backend_cold: Array<ClusterListNode>;
  doris_backend_hot: Array<ClusterListNode>;
  doris_follower: Array<ClusterListNode>;
  doris_observer: Array<ClusterListNode>;
  id: number;
  major_version: string;
  operations: ClusterListOperation[];
  permission: {
    access_entry_edit: boolean;
    doris_access_entry_view: boolean;
    doris_destroy: boolean;
    doris_enable_disable: boolean;
    doris_reboot: boolean;
    doris_replace: boolean;
    doris_scale_up: boolean;
    doris_shrink: boolean;
    doris_view: boolean;
  };
  phase: 'online' | 'offline';
  phase_name: string;
  region: string;
  status: string;
  update_at: string;
  updater: string;

  constructor(payload = {} as Doris) {
    super(payload);
    this.bk_biz_id = payload.bk_biz_id;
    this.bk_biz_name = payload.bk_biz_name;
    this.bk_cloud_id = payload.bk_cloud_id;
    this.bk_cloud_name = payload.bk_cloud_name;
    this.bk_sub_zone = payload.bk_sub_zone;
    this.cluster_access_port = payload.cluster_access_port;
    this.cluster_alias = payload.cluster_alias;
    this.cluster_entry = payload.cluster_entry;
    this.cluster_name = payload.cluster_name;
    this.cluster_spec = payload.cluster_spec || {};
    this.cluster_stats = payload.cluster_stats || {};
    this.cluster_type = payload.cluster_type;
    this.cluster_type_name = payload.cluster_type_name;
    this.cluster_time_zone = payload.cluster_time_zone;
    this.create_at = payload.create_at;
    this.creator = payload.creator;
    this.disaster_tolerance_level = payload.disaster_tolerance_level;
    this.domain = payload.domain;
    this.doris_backend_cold = payload.doris_backend_cold;
    this.doris_backend_hot = payload.doris_backend_hot;
    this.doris_follower = payload.doris_follower;
    this.doris_observer = payload.doris_observer;
    this.id = payload.id;
    this.major_version = payload.major_version;
    this.operations = payload.operations || [];
    this.permission = payload.permission || {};
    this.phase = payload.phase;
    this.phase_name = payload.phase_name;
    this.region = payload.region;
    this.status = payload.status;
    this.update_at = payload.update_at;
    this.updater = payload.updater;
    this.access_url = payload.access_url;
  }

  get runningOperation() {
    const operateTicketTypes = Object.keys(Doris.operationTextMap);
    return this.operations.find((item) => operateTicketTypes.includes(item.ticket_type) && item.status === 'RUNNING');
  }

  // 操作中的状态
  get operationRunningStatus() {
    if (this.operations.length < 1) {
      return '';
    }
    const operation = this.runningOperation;
    if (!operation) {
      return '';
    }
    return operation.ticket_type;
  }

  // 操作中的状态描述文本
  get operationStatusText() {
    return Doris.operationTextMap[this.operationRunningStatus];
  }

  // 操作中的状态 icon
  get operationStatusIcon() {
    return Doris.operationIconMap[this.operationRunningStatus];
  }

  // 操作中的单据 ID
  get operationTicketId() {
    if (this.operations.length < 1) {
      return 0;
    }
    const operation = this.runningOperation;
    if (!operation) {
      return 0;
    }
    return operation.ticket_id;
  }

  get operationDisabled() {
    // 集群异常不支持操作
    if (this.isAbnormal) {
      return true;
    }
    // 被禁用的集群不支持操作
    if (this.phase !== 'online') {
      return true;
    }
    // 各个操作互斥，有其他任务进行中禁用操作按钮
    if (this.operationRunningStatus) {
      return true;
    }
    return false;
  }

  get operationTagTips() {
    return this.operations.map((item) => ({
      icon: Doris.operationIconMap[item.ticket_type],
      tip: Doris.operationTextMap[item.ticket_type],
      ticketId: item.ticket_id,
    }));
  }

  get isStarting() {
    return Boolean(this.operations.find((item) => item.ticket_type === Doris.DORIS_ENABLE));
  }

  get masterDomainDisplayName() {
    const port = this.doris_follower[0]?.port;
    const displayName = port ? `${this.domain}:${port}` : this.domain;
    return displayName;
  }

  get isAbnormal() {
    return this.status === STATUS_ABNORMAL;
  }

  get allInstanceList() {
    return [...this.doris_follower, ...this.doris_observer, ...this.doris_backend_cold, ...this.doris_backend_hot];
  }

  get allIPList() {
    return uniq(this.allInstanceList.map((item) => item.ip));
  }

  // 异常主机IP
  get allUnavailableIPList() {
    return uniq(
      this.allInstanceList.reduce(
        (pre, cur) => [...pre, ...(cur.status === 'unavailable' ? [cur.ip] : [])],
        [] as string[],
      ),
    );
  }

  get disasterToleranceLevelName() {
    return ClusterAffinityMap[this.disaster_tolerance_level];
  }

  get roleFailedInstanceInfo() {
    return {
      Follower: ClusterBase.getRoleFaildInstanceList(this.doris_follower),
      Observer: ClusterBase.getRoleFaildInstanceList(this.doris_observer),
      [t('热节点')]: ClusterBase.getRoleFaildInstanceList(this.doris_backend_hot),
      [t('冷节点')]: ClusterBase.getRoleFaildInstanceList(this.doris_backend_cold),
    };
  }
}
