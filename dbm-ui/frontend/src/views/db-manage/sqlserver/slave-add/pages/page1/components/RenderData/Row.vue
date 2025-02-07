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
  <tbody>
    <tr>
      <FixedColumn fixed="left">
        <RenderCluster
          ref="clusterRef"
          v-model="localClusterData" />
      </FixedColumn>
      <td style="padding: 0">
        <RenderSlaveHost
          ref="hostRef"
          :cluster-data="localClusterData"
          :model-value="localNewSlaveHost" />
      </td>
      <OperateColumn
        :removeable="removeable"
        @add="handleAppend"
        @remove="handleRemove" />
    </tr>
  </tbody>
</template>
<script lang="ts">
  import { ref, watch } from 'vue';

  import FixedColumn from '@components/render-table/columns/fixed-column/index.vue';
  import OperateColumn from '@components/render-table/columns/operate-column/index.vue';

  import RenderCluster from '@views/db-manage/sqlserver/common/RenderCluster.vue';

  import { random } from '@utils';

  import RenderSlaveHost from './RenderSlaveHost.vue';

  export interface IHostData {
    bk_biz_id: number;
    bk_host_id: number;
    ip: string;
    bk_cloud_id: number;
  }
  export interface IDataRow {
    rowKey: string;
    clusterData?: {
      id: number;
      domain: string;
      cloudId: number;
    };
    newSlaveHost?: IHostData;
  }

  // 创建表格数据
  export const createRowData = (data = {} as Partial<IDataRow>) => ({
    rowKey: random(),
    clusterData: data.clusterData,
    newSlaveHost: data.newSlaveHost,
  });
</script>
<script setup lang="ts">
  interface Props {
    data: IDataRow;
    removeable: boolean;
  }
  interface Emits {
    (e: 'add', params: Array<IDataRow>): void;
    (e: 'remove'): void;
  }

  interface Exposes {
    getValue: () => Promise<any>;
  }

  const props = defineProps<Props>();

  const emits = defineEmits<Emits>();

  const clusterRef = ref<InstanceType<typeof RenderCluster>>();
  const hostRef = ref<InstanceType<typeof RenderSlaveHost>>();

  const localClusterData = ref<IDataRow['clusterData']>();
  const localNewSlaveHost = ref<IDataRow['newSlaveHost']>();

  watch(
    () => props.data,
    () => {
      localClusterData.value = props.data.clusterData;
      localNewSlaveHost.value = props.data.newSlaveHost;
    },
    {
      immediate: true,
    },
  );

  const handleAppend = () => {
    emits('add', [createRowData()]);
  };

  const handleRemove = () => {
    if (props.removeable) {
      return;
    }
    emits('remove');
  };

  defineExpose<Exposes>({
    getValue() {
      return Promise.all([clusterRef.value!.getValue('cluster_ids'), hostRef.value!.getValue()]).then(
        ([, hostData]) => ({
          cluster_ids: [localClusterData.value!.id],
          ...hostData,
        }),
      );
    },
  });
</script>
<style lang="less" scoped>
  .action-box {
    display: flex;
    align-items: center;

    .action-btn {
      display: flex;
      font-size: 14px;
      color: #c4c6cc;
      cursor: pointer;
      transition: all 0.15s;

      &:hover {
        color: #979ba5;
      }

      &.disabled {
        color: #dcdee5;
        cursor: not-allowed;
      }

      & ~ .action-btn {
        margin-left: 18px;
      }
    }
  }
</style>
