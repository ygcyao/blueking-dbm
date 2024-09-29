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
import TicketModel, { type Redis } from '@services/model/ticket/ticket';

import { random } from '@utils';

// Redis 整机替换
export function generateRedisClusterCutoffCloneData(ticketData: TicketModel<Redis.ClusterCutoff>) {
  const { clusters, infos, specs } = ticketData.details;
  return Promise.resolve({
    tableDataList: infos.flatMap((info) =>
      info.display_info.data.map((curr) => ({
        rowKey: random(),
        isLoading: false,
        ip: curr.ip,
        role: curr.role,
        clusterIds: info.cluster_ids,
        bkCloudId: info.bk_cloud_id,
        cluster: {
          domain: info.cluster_ids.map((id) => clusters[id].immute_domain).join(','),
          isStart: false,
          isGeneral: true,
          rowSpan: 1,
        },
        spec: specs[curr.spec_id],
      })),
    ),
    remark: ticketData.remark,
  });
}
