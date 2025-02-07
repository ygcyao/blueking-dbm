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
import pinyin from 'tiny-pinyin';

import type { BizItem } from '@services/types';

import http from '../http';

const path = '/apis/cmdb';

/**
 * 业务列表
 */
export function getBizs(params = {} as { action: string }) {
  return http.get<BizItem[]>(`${path}/list_bizs/`, params).then((res) =>
    res.map((item: BizItem) => {
      const biz = { ...item };
      biz.display_name = `[${item.bk_biz_id}] ${item.name}`;
      const parseName = pinyin.parse(item.name);
      const names = [];
      const heads = [];
      for (const word of parseName) {
        const { type, target } = word;
        names.push(target);
        heads.push(type === 2 ? target[0] : target);
      }
      biz.pinyin_head = heads.join('');
      biz.pinyin_name = names.join('');

      return biz;
    }),
  );
}

/**
 * 创建数据库模块
 */
export function createModules(params: {
  db_module_name: string;
  alias_name: string;
  cluster_type: string;
  biz_id: number;
}) {
  return http.post<{
    db_module_id: number;
    db_module_name: string;
    cluster_type: string;
    bk_biz_id: number;
    bk_set_id: number;
    bk_modules: {
      bk_module_name: string;
      bk_module_id: string;
    }[];
    name: string;
  }>(`${path}/${params.biz_id}/create_module/`, params);
}

/**
 * 查询 CC 角色对象
 */
export function getUserGroupList(params: { bk_biz_id: number }) {
  return http.get<
    {
      id: string;
      display_name: string;
      logo: string;
      type: string;
      members: string[];
      disabled?: boolean;
    }[]
  >(`${path}/${params.bk_biz_id}/list_cc_obj_user/`);
}

/**
 * 业务下的模块列表
 */
export function getModules(params: { bk_biz_id: number; cluster_type: string }) {
  return http.get<
    {
      alias_name: string;
      bk_biz_id: number;
      db_module_id: number;
      name: string;
      db_module_info: {
        version: string;
        name: string;
        description: string;
        updated_at: string;
        updated_by: string;
        conf_items: {
          conf_name: string;
          conf_value: string;
          description: string;
          flag_disable: number;
          flag_locked: number;
          stage: number;
          level_name: string;
          level_value: string;
          op_type: string;
          value_allowed: string;
          need_restart: number;
          value_type_sub: string;
        }[];
      };
      permission: {
        dbconfig_view: boolean;
      };
    }[]
  >(`${path}/${params.bk_biz_id}/list_modules/`, params);
}

/**
 * 设置业务英文缩写
 */
export function createAppAbbr(params: { db_app_abbr: string; id: number }) {
  return http.post<{
    db_app_abbr: string;
  }>(`${path}/${params.id}/set_db_app_abbr/`, params);
}
