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
  <SmartAction>
    <div class="db-table-backup-page">
      <BkAlert
        closable
        theme="info"
        :title="t('指定库表备份_支持模糊匹配')" />
      <div class="mt16">
        <BkButton @click="handleShowBatchEntry">
          <DbIcon type="add" />
          {{ t('批量录入') }}
        </BkButton>
      </div>
      <RenderData
        class="mt16"
        @batch-edit="handleBatchEditColumn"
        @batch-select-cluster="handleShowBatchSelector">
        <RenderDataRow
          v-for="(item, index) in tableData"
          :key="item.rowKey"
          ref="rowRefs"
          :data="item"
          :removeable="tableData.length < 2"
          @add="(payload: Array<IDataRow>) => handleAppend(index, payload)"
          @clone="(payload: IDataRow) => handleClone(index, payload)"
          @id-change="(clusterId: number) => handleChangeCluster(index, clusterId)"
          @remove="handleRemove(index)" />
      </RenderData>
      <TicketRemark v-model="remark" />
      <ClusterSelector
        v-model:is-show="isShowBatchSelector"
        :cluster-types="[ClusterTypes.TENDBHA, ClusterTypes.TENDBSINGLE]"
        :selected="selectedClusters"
        @change="handelClusterChange" />
      <BatchEntry
        v-model:is-show="isShowBatchEntry"
        @change="handleBatchEntry" />
    </div>
    <template #action>
      <BkButton
        class="w-88"
        :loading="isSubmitting"
        theme="primary"
        @click="handleSubmit">
        {{ t('提交') }}
      </BkButton>
      <DbPopconfirm
        :confirm-handler="handleReset"
        :content="t('重置将会清空当前填写的所有内容_请谨慎操作')"
        :title="t('确认重置页面')">
        <BkButton
          class="ml8 w-88"
          :disabled="isSubmitting">
          {{ t('重置') }}
        </BkButton>
      </DbPopconfirm>
    </template>
  </SmartAction>
</template>

<script setup lang="tsx">
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import TendbhaModel from '@services/model/mysql/tendbha';
  import TendbsingleModel from '@services/model/mysql/tendbsingle';
  import { filterClusters } from '@services/source/dbbase';
  import { createTicket } from '@services/source/ticket';

  import { useTicketCloneInfo } from '@hooks';

  import { useGlobalBizs } from '@stores';

  import { ClusterTypes, TicketTypes } from '@common/const';

  import ClusterSelector from '@components/cluster-selector/Index.vue';
  import TicketRemark from '@components/ticket-remark/Index.vue';

  import BatchEntry, { type IValue as IBatchEntryValue } from './components/BatchEntry.vue';
  import RenderData from './components/RenderData/Index.vue';
  import RenderDataRow, { createRowData, type IDataRow, type IDataRowBatchKey } from './components/RenderData/Row.vue';

  // 检测列表是否为空
  const checkListEmpty = (list: Array<IDataRow>) => {
    if (list.length > 1) {
      return false;
    }

    const [firstRow] = list;
    return (
      !firstRow.clusterData &&
      // && !firstRow.backupOn
      !firstRow.dbPatterns &&
      !firstRow.ignoreDbs &&
      !firstRow.tablePatterns &&
      !firstRow.ignoreTables
    );
  };

  const router = useRouter();
  const { currentBizId } = useGlobalBizs();
  const { t } = useI18n();

  // 单据克隆
  useTicketCloneInfo({
    type: TicketTypes.MYSQL_HA_DB_TABLE_BACKUP,
    onSuccess(cloneData) {
      tableData.value = cloneData.tableDataList;
      remark.value = cloneData.remark;
      window.changeConfirm = true;
    },
  });

  const rowRefs = ref();
  const isShowBatchSelector = ref(false);
  const isShowBatchEntry = ref(false);
  const isSubmitting = ref(false);
  const tableData = ref<Array<IDataRow>>([createRowData({})]);
  const remark = ref('');

  const selectedClusters = shallowRef<{ [key: string]: Array<TendbhaModel | TendbsingleModel> }>({
    [ClusterTypes.TENDBHA]: [],
    [ClusterTypes.TENDBSINGLE]: [],
  });

  // 集群域名是否已存在表格的映射表
  let domainMemo: Record<string, boolean> = {};

  // 批量录入
  const handleShowBatchEntry = () => {
    isShowBatchEntry.value = true;
  };
  // 批量录入
  const handleBatchEntry = (list: Array<IBatchEntryValue>) => {
    const newList = list.map((item) => createRowData(item));
    if (checkListEmpty(tableData.value)) {
      tableData.value = newList;
    } else {
      tableData.value = [...tableData.value, ...newList];
    }
    window.changeConfirm = true;
  };
  // 批量选择
  const handleShowBatchSelector = () => {
    isShowBatchSelector.value = true;
  };
  // 批量选择
  const handelClusterChange = (selected: Record<string, Array<TendbhaModel | TendbsingleModel>>) => {
    selectedClusters.value = selected;
    const newList = [...selected[ClusterTypes.TENDBHA], ...selected[ClusterTypes.TENDBSINGLE]].reduce(
      (results, clusterData) => {
        const domain = clusterData.master_domain;
        if (!domainMemo[domain]) {
          const row = createRowData({
            clusterData: {
              id: clusterData.id,
              domain: clusterData.master_domain,
            },
            backupLocal: clusterData.cluster_type === ClusterTypes.TENDBHA ? 'Slave' : 'Master',
          });
          results.push(row);
          domainMemo[domain] = true;
        }
        return results;
      },
      [] as IDataRow[],
    );

    if (checkListEmpty(tableData.value)) {
      tableData.value = newList;
    } else {
      tableData.value = [...tableData.value, ...newList];
    }
    window.changeConfirm = true;
  };

  // 输入集群后查询集群信息并填充到table
  const handleChangeCluster = async (index: number, clusterId: number) => {
    if (tableData.value[index].clusterData?.id === clusterId) {
      return;
    }

    const resultList = await filterClusters<TendbhaModel | TendbsingleModel>({
      bk_biz_id: window.PROJECT_CONFIG.BIZ_ID,
      cluster_ids: String(clusterId),
    });
    if (resultList.length < 1) {
      return;
    }
    const item = resultList[0];
    const domain = item.master_domain;
    const row = createRowData({
      clusterData: {
        id: item.id,
        domain,
      },
      backupLocal: item.cluster_type === ClusterTypes.TENDBHA ? 'Slave' : 'Master',
    });
    tableData.value[index] = row;
    domainMemo[domain] = true;
    selectedClusters.value[item.cluster_type].push(item);
  };

  const handleBatchEditColumn = (value: string | string[], filed: IDataRowBatchKey) => {
    if (!value || checkListEmpty(tableData.value)) {
      return;
    }
    tableData.value.forEach((row) => {
      Object.assign(row, {
        [filed]: value,
      });
    });
  };

  // 追加一个集群
  const handleAppend = (index: number, appendList: Array<IDataRow>) => {
    const dataList = [...tableData.value];
    dataList.splice(index + 1, 0, ...appendList);
    tableData.value = dataList;
  };

  // 删除一个集群
  const handleRemove = (index: number) => {
    const dataList = [...tableData.value];
    const domain = dataList[index].clusterData?.domain;
    if (domain) {
      delete domainMemo[domain];
      const haList = selectedClusters.value[ClusterTypes.TENDBHA];
      selectedClusters.value[ClusterTypes.TENDBHA] = haList.filter((item) => item.master_domain !== domain);
      const singleList = selectedClusters.value[ClusterTypes.TENDBSINGLE];
      selectedClusters.value[ClusterTypes.TENDBSINGLE] = singleList.filter((item) => item.master_domain !== domain);
    }
    dataList.splice(index, 1);
    tableData.value = dataList;
  };

  // 复制行数据
  const handleClone = (index: number, sourceData: IDataRow) => {
    const dataList = [...tableData.value];
    dataList.splice(index + 1, 0, sourceData);
    tableData.value = dataList;
    setTimeout(() => {
      rowRefs.value[rowRefs.value.length - 1].getValue();
    });
  };

  const handleSubmit = async () => {
    try {
      isSubmitting.value = true;
      const infos = await Promise.all(rowRefs.value.map((item: { getValue: () => Promise<any> }) => item.getValue()));
      await createTicket({
        ticket_type: 'MYSQL_HA_DB_TABLE_BACKUP',
        remark: remark.value,
        details: {
          infos,
        },
        bk_biz_id: currentBizId,
      }).then((data) => {
        window.changeConfirm = false;
        router.push({
          name: 'MySQLDBTableBackup',
          params: {
            page: 'success',
          },
          query: {
            ticketId: data.id,
          },
        });
      });
    } finally {
      isSubmitting.value = false;
    }
  };

  const handleReset = () => {
    tableData.value = [createRowData()];
    remark.value = '';
    selectedClusters.value[ClusterTypes.TENDBHA] = [];
    selectedClusters.value[ClusterTypes.TENDBSINGLE] = [];
    domainMemo = {};
    window.changeConfirm = false;
  };
</script>

<style lang="less">
  .db-table-backup-page {
    padding-bottom: 20px;
  }
</style>
