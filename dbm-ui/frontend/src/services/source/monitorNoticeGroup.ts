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

import NoticGroupModel from '@services/model/notice-group/notice-group';
import type { ListBase } from '@services/types';

import http, { type IRequestPayload } from '../http';

const path = '/apis/monitor/notice_group';

/**
 * 获取告警组列表
 */
export function getAlarmGroupList(
  params: {
    bk_biz_id: number;
    name: string;
    limit: number;
    offset: number;
  },
  payload = {} as IRequestPayload,
) {
  return http.get<ListBase<NoticGroupModel[]>>(`${path}/`, params, payload).then((data) => ({
    ...data,
    results: data.results.map(
      (item) =>
        new NoticGroupModel(
          Object.assign(item, {
            permission: Object.assign(item.permission, data.permission),
          }),
        ),
    ),
  }));
}

/**
 * 新建告警组
 */
export function insertAlarmGroup(params: {
  bk_biz_id: number;
  name: string;
  receivers: NoticGroupModel['receivers'][];
  details: NoticGroupModel['details'];
}) {
  return http.post(`${path}/`, params);
}

/**
 * 编辑告警组(全量)
 */
export function updateAlarmGroup(params: {
  name: string;
  bk_biz_id: number;
  receivers: NoticGroupModel['receivers'][];
  details: NoticGroupModel['details'];
  id: number;
}) {
  return http.put(`${path}/${params.id}/`, params);
}

/**
 * 编辑告警组(部分)
 */
export function patchAlarmGroup(params: {
  name: string;
  receivers: NoticGroupModel['receivers'][];
  details: NoticGroupModel['details'];
  id: number;
}) {
  return http.patch(`${path}/${params.id}/`, params);
}

/**
 * 删除告警组
 */
export function deleteAlarmGroup(params: { id: number }) {
  return http.delete(`${path}/${params.id}/`);
}

/**
 * 获取告警组通知方式
 */
export function getAlarmGroupNotifyList(params: { bk_biz_id: number; name?: string; limit?: number; offset?: number }) {
  return http.get<
    {
      type: string;
      label: string;
      is_active: boolean;
      icon: string;
    }[]
  >(`${path}/get_msg_type/`, params);
}

export function getSimpleList(params: { bk_biz_id: number; db_type: string }) {
  return http.get<
    {
      id: string;
      name: string;
      receivers: {
        id: string;
        type: string;
      }[];
    }[]
  >(`${path}/list_group_name/`, params);
}
