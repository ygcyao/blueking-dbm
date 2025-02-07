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
    <div class="spider-manage-db-table-backup-page">
      <BkAlert
        closable
        theme="info"
        :title="t('库表备份：指定库表备份，支持模糊匹配')" />
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
        :cluster-types="[ClusterTypes.TENDBCLUSTER]"
        :selected="selectedClusters"
        @change="handelClusterChange" />
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

  import TendbClusterModel from '@services/model/tendbcluster/tendbcluster';
  import { getTendbClusterList } from '@services/source/tendbcluster';
  import { createTicket } from '@services/source/ticket';

  import { useTicketCloneInfo } from '@hooks';

  import { useGlobalBizs } from '@stores';

  import { ClusterTypes, TicketTypes } from '@common/const';

  import ClusterSelector from '@components/cluster-selector/Index.vue';
  import TicketRemark from '@components/ticket-remark/Index.vue';

  import RenderData from './components/RenderData/Index.vue';
  import RenderDataRow, { createRowData, type IDataRow, type IDataRowBatchKey } from './components/RenderData/Row.vue';

  const { t } = useI18n();
  const router = useRouter();
  const { currentBizId } = useGlobalBizs();

  // 单据克隆
  useTicketCloneInfo({
    type: TicketTypes.TENDBCLUSTER_DB_TABLE_BACKUP,
    onSuccess(cloneData) {
      tableData.value = cloneData.tableDataList;
      remark.value = cloneData.remark;
      window.changeConfirm = true;
    },
  });

  const rowRefs = ref();
  const isShowBatchSelector = ref(false);
  const isSubmitting = ref(false);
  const tableData = ref<Array<IDataRow>>([createRowData({})]);
  const remark = ref('');

  const selectedClusters = shallowRef<{ [key: string]: Array<TendbClusterModel> }>({ [ClusterTypes.TENDBCLUSTER]: [] });

  // 集群域名是否已存在表格的映射表
  let domainMemo: Record<string, boolean> = {};

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

  // 批量选择
  const handleShowBatchSelector = () => {
    isShowBatchSelector.value = true;
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

  // 批量选择
  const handelClusterChange = (selected: { [key: string]: Array<TendbClusterModel> }) => {
    selectedClusters.value = selected;
    const list = selected[ClusterTypes.TENDBCLUSTER];
    const newList = list.reduce((result, item) => {
      const domain = item.master_domain;
      if (!domainMemo[domain]) {
        const row = createRowData({
          clusterData: {
            id: item.id,
            domain: item.master_domain,
          },
        });
        result.push(row);
        domainMemo[domain] = true;
      }
      return result;
    }, [] as IDataRow[]);
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

    const resultList = await getTendbClusterList({
      cluster_ids: [clusterId],
    });
    if (resultList.results.length < 1) {
      return;
    }
    const item = resultList.results[0];
    const domain = item.master_domain;
    const row = createRowData({
      clusterData: {
        id: item.id,
        domain: item.master_domain,
      },
    });
    tableData.value[index] = row;
    domainMemo[domain] = true;
    selectedClusters.value[item.cluster_type].push(item);
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
    dataList.splice(index, 1);
    tableData.value = dataList;
    if (domain) {
      delete domainMemo[domain];
      const clustersArr = selectedClusters.value[ClusterTypes.TENDBCLUSTER];
      selectedClusters.value[ClusterTypes.TENDBCLUSTER] = clustersArr.filter((item) => item.master_domain !== domain);
    }
  };

  // 复制行数据
  const handleClone = (index: number, sourceData: IDataRow) => {
    const dataList = [...tableData.value];
    dataList.splice(
      index + 1,
      0,
      Object.assign(sourceData, {
        clusterData: {
          ...sourceData.clusterData,
          domain: tableData.value[index].clusterData?.domain ?? '',
        },
      }),
    );
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
        ticket_type: TicketTypes.TENDBCLUSTER_DB_TABLE_BACKUP,
        remark: remark.value,
        details: {
          infos,
        },
        bk_biz_id: currentBizId,
      }).then((data) => {
        window.changeConfirm = false;
        router.push({
          name: 'spiderDbTableBackup',
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
    remark.value = '';
    tableData.value = [createRowData()];
    selectedClusters.value[ClusterTypes.TENDBCLUSTER] = [];
    domainMemo = {};
    window.changeConfirm = false;
  };
</script>

<style lang="less">
  .spider-manage-db-table-backup-page {
    padding-bottom: 20px;
  }
</style>
