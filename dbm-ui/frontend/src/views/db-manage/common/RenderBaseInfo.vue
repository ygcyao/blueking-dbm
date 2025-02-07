<!--
 * TencentBlueKing is pleased to support the open source community by making 蓝鲸智云-DB管理系统(BlueKing-BK-DBM) available.
 *
 * Copyright (C) 2017-2023 THL A29 Limited, a Tencent company. All rights reserved.
 *
 * Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
 * You may obtain a copy of the License athttps://opensource.org/licenses/MIT
 *
 * Unless required by applicable law or agreed to in writing, software distributed under the License is distributed
 * on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for
 * the specific language governing permissions and limitations under the License.
-->

<template>
  <div class="render-cluster-base-info">
    <table>
      <tbody>
        <tr>
          <td>ID：</td>
          <td>{{ data.id }}</td>
          <td>{{ $t('状态') }}：</td>
          <td>
            <RenderClusterStatus
              v-if="data.status"
              :data="data.status" />
          </td>
        </tr>
        <tr>
          <td>{{ $t('集群名称') }}：</td>
          <td>
            {{ data.cluster_name }}
            <span
              v-if="data.cluster_alias"
              style="color: #63656e">
              ({{ data.cluster_alias }})
            </span>
          </td>
          <td>{{ $t('域名') }}：</td>
          <td>{{ data.domain }}</td>
        </tr>
        <tr>
          <td>{{ $t('所属业务') }}：</td>
          <td>{{ displayBizName }}</td>
          <td>{{ $t('数据版本') }}：</td>
          <td>{{ data.major_version }}</td>
        </tr>
        <tr>
          <td>{{ $t('创建时间') }}：</td>
          <td>{{ data.create_at }}</td>
          <td>{{ $t('容灾要求') }}：</td>
          <td>{{ data.disasterToleranceLevelName || '--' }}</td>
        </tr>
        <tr>
          <td>{{ $t('地域') }}：</td>
          <td>{{ data.region || '--' }}</td>
          <td>{{ $t('规格') }}：</td>
          <td>{{ data.cluster_spec.spec_name || '--' }}</td>
        </tr>
        <tr>
          <td>{{ $t('管控区域') }}：</td>
          <td>{{ data.bk_cloud_name ? `${data.bk_cloud_name}[${data.bk_cloud_id}]` : '--' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
<script setup lang="ts">
  import RenderClusterStatus from '@components/cluster-status/Index.vue';

  interface Props {
    data: Record<any, any> & { id: number };
  }

  const props = defineProps<Props>();

  const displayBizName = computed(() => {
    const { bk_biz_id: id, bk_biz_name: name } = props.data;
    if (id && name) {
      return `[${id}] ${name}`;
    }

    return name || id || '--';
  });
</script>
<style lang="less">
  .render-cluster-base-info {
    padding-top: 20px;

    table {
      width: 100%;
      font-size: 12px;
      line-height: 28px;
      color: #63656e;

      td:nth-child(2n + 1) {
        text-align: right;
      }

      td:nth-child(2n) {
        color: #313238;
      }
    }
  }
</style>
