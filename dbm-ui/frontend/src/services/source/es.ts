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

import EsModel from '@services/model/es/es';
import EsDetailModel from '@services/model/es/es-detail';
import EsInstanceModel from '@services/model/es/es-instance';
import EsMachineModel from '@services/model/es/es-machine';
import EsNodeModel from '@services/model/es/es-node';
import EsPasswordModel from '@services/model/es/es-password';
import type { ListBase } from '@services/types';

import { useGlobalBizs } from '@stores';

import http from '../http';

const { currentBizId } = useGlobalBizs();

const path = `/apis/bigdata/bizs/${currentBizId}/es/es_resources`;

/**
 * 获取集群列表
 */
export function getEsList(params: Record<string, any> & { bk_biz_id: number }) {
  return http.get<ListBase<EsModel[]>>(`${path}/`, params).then((data) => ({
    ...data,
    results: data.results.map(
      (item: EsModel) =>
        new EsModel(
          Object.assign(item, {
            permission: Object.assign({}, item.permission, data.permission),
          }),
        ),
    ),
  }));
}

/**
 * 获取查询返回字段
 */
export function getEsTableFields() {
  return http.get<ListBase<EsModel[]>>(`${path}/get_table_fields/`);
}

/**
 * 获取实例列表
 */
export function getEsInstanceList(params: Record<string, any> & { bk_biz_id: number }) {
  return http.get<ListBase<EsInstanceModel[]>>(`${path}/list_instances/`, params).then((data) => ({
    ...data,
    results: data.results.map((item) => new EsInstanceModel(item)),
  }));
}

/**
 * 获取实例详情
 */
export function retrieveEsInstance(params: { bk_biz_id: number }) {
  return http.get<ListBase<EsModel[]>>(`${path}/retrieve_instance/`, params);
}

/**
 * 获取集群详情
 */
export function getEsDetail(params: { id: number }) {
  return http.get<EsDetailModel>(`${path}/${params.id}/`).then((data) => new EsDetailModel(data));
}

/**
 * 获取集群拓扑
 */
export function getEsTopoGraph(params: { cluster_id: number }) {
  return http.get<ListBase<EsModel[]>>(`${path}/${params.cluster_id}/get_topo_graph/`);
}

/**
 * 获取 ES 集群访问密码
 */
export function getEsPassword(params: { cluster_id: number }) {
  return http
    .get<EsPasswordModel>(`${path}/${params.cluster_id}/get_password/`)
    .then((data) => new EsPasswordModel(data));
}

/**
 * 获取 ES 集群节点列表信息
 */
export function getEsNodeList(
  params: Record<string, any> & {
    bk_biz_id: number;
    cluster_id: number;
  },
) {
  return http.get<ListBase<Array<EsNodeModel>>>(`${path}/${params.cluster_id}/list_nodes/`, params).then((data) => ({
    ...data,
    results: data.results.map(
      (item) =>
        new EsNodeModel(
          Object.assign(item, {
            permission: data.permission,
          }),
        ),
    ),
  }));
}

/**
 * 导出集群数据为 excel 文件
 */
export function exportEsClusterToExcel(params: { cluster_ids?: number[] }) {
  return http.post<string>(`${path}/export_cluster/`, params, { responseType: 'blob' });
}

/**
 * 导出实例数据为 excel 文件
 */
export function exportEsInstanceToExcel(params: { bk_host_ids?: number[] }) {
  return http.post<string>(`${path}/export_instance/`, params, { responseType: 'blob' });
}

/**
 * 查询主机列表
 */
export function getEsMachineList(params: {
  limit?: number;
  offset?: number;
  bk_host_id?: number;
  ip?: string;
  cluster_ids?: string;
  bk_city_name?: string;
  machine_type?: string;
  bk_os_name?: string;
  bk_cloud_id?: number;
  bk_agent_id?: string;
  instance_role?: string;
  creator?: string;
  add_role_count?: boolean;
  cluster_type?: string;
}) {
  return http.get<ListBase<EsMachineModel[]>>(`${path}/list_machines/`, params).then((data) => ({
    ...data,
    results: data.results.map((item) => new EsMachineModel(item)),
  }));
}
