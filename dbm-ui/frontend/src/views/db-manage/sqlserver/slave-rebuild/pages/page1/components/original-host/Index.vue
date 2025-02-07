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
    <div class="sqlserver-slave-rebuild-original-host-box">
      <RenderData
        class="mt16"
        @show-ip-selector="handleShowIpSelector">
        <RenderDataRow
          v-for="(item, index) in tableData"
          :key="item.rowKey"
          ref="rowRefs"
          :data="item"
          :removeable="tableData.length < 2"
          @add="(payload: Array<IDataRow>) => handleAppend(index, payload)"
          @remove="handleRemove(index)" />
      </RenderData>
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
        :content="t('重置将会情况当前填写的所有内容_请谨慎操作')"
        :title="t('确认重置页面')">
        <BkButton
          class="ml8 w-88"
          :disabled="isSubmitting">
          {{ t('重置') }}
        </BkButton>
      </DbPopconfirm>
    </template>
    <InstanceSelector
      v-model:is-show="isShowInstanceSelecotr"
      :cluster-types="[ClusterTypes.SQLSERVER_HA]"
      :selected="instanceSelectValue"
      :tab-list-config="tabListConfig"
      @change="handleInstancesChange" />
  </SmartAction>
</template>
<script setup lang="tsx">
  import { ref, type UnwrapRef } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import { getSqlServerInstanceList } from '@services/source/sqlserveHaCluster';
  import { createTicket } from '@services/source/ticket';

  import { useTicketCloneInfo } from '@hooks';

  import { ClusterTypes, TicketTypes } from '@common/const';

  import InstanceSelector, {
    type InstanceSelectorValues,
    type IValue,
    type PanelListType,
  } from '@components/instance-selector/Index.vue';

  import RenderData from './components/RenderData/Index.vue';
  import RenderDataRow, { createRowData, type IDataRow } from './components/RenderData/Row.vue';

  const { t } = useI18n();
  const router = useRouter();

  useTicketCloneInfo({
    type: TicketTypes.SQLSERVER_RESTORE_LOCAL_SLAVE,
    onSuccess(data) {
      tableData.value = data.map((item) =>
        createRowData({
          slave: {
            bkCloudId: item.slave.bk_cloud_id,
            bkHostId: item.slave.bk_host_id,
            ip: item.slave.ip,
            port: item.slave.port,
            instanceAddress: `${item.slave.ip}:${item.slave.port}`,
          },
        }),
      );
    },
  });

  const tabListConfig = {
    [ClusterTypes.SQLSERVER_HA as string]: [
      {
        name: t('从库实例'),
        tableConfig: {
          getTableList: (params: ServiceParameters<typeof getSqlServerInstanceList>) =>
            getSqlServerInstanceList({
              ...params,
              role: 'backend_slave',
            }),
        },
      },
    ],
  } as Record<string, PanelListType>;

  const isShowInstanceSelecotr = ref(false);
  const rowRefs = ref([] as InstanceType<typeof RenderDataRow>[]);
  const isSubmitting = ref(false);
  const instanceSelectValue = shallowRef<InstanceSelectorValues<IValue>>({
    [ClusterTypes.SQLSERVER_HA]: [],
  });

  const tableData = shallowRef<Array<IDataRow>>([createRowData({})]);

  // 检测列表是否为空
  const checkListEmpty = (list: Array<IDataRow>) => {
    if (list.length > 1) {
      return false;
    }
    const [firstRow] = list;
    return !firstRow.slave && !firstRow.clusterId;
  };

  // Master 批量选择
  const handleShowIpSelector = () => {
    isShowInstanceSelecotr.value = true;
  };

  const handleInstancesChange = (selected: UnwrapRef<typeof instanceSelectValue>) => {
    instanceSelectValue.value = selected;
    const newList = selected[ClusterTypes.SQLSERVER_HA].map((instanceData) =>
      createRowData({
        slave: {
          bkCloudId: instanceData.bk_cloud_id,
          bkHostId: instanceData.bk_host_id,
          ip: instanceData.ip,
          port: instanceData.port,
          instanceAddress: instanceData.instance_address,
        },
      }),
    );

    if (checkListEmpty(tableData.value)) {
      tableData.value = newList;
    } else {
      tableData.value = [...tableData.value, ...newList];
    }
    window.changeConfirm = true;
  };

  // 追加一个行
  const handleAppend = (index: number, appendList: Array<IDataRow>) => {
    const dataList = [...tableData.value];
    dataList.splice(index + 1, 0, ...appendList);
    tableData.value = dataList;
  };

  // 删除一个行
  const handleRemove = (index: number) => {
    const dataList = [...tableData.value];
    dataList.splice(index, 1);
    tableData.value = dataList;
  };

  const handleSubmit = () => {
    isSubmitting.value = true;
    Promise.all(rowRefs.value.map((item) => item.getValue()))
      .then((data) =>
        createTicket({
          ticket_type: TicketTypes.SQLSERVER_RESTORE_LOCAL_SLAVE,
          remark: '',
          details: {
            backup_source: 'manual_input',
            infos: data,
          },
          bk_biz_id: window.PROJECT_CONFIG.BIZ_ID,
        }).then((data) => {
          window.changeConfirm = false;

          router.push({
            name: 'sqlServerSlaveRebuild',
            params: {
              page: 'success',
            },
            query: {
              ticketId: data.id,
            },
          });
        }),
      )
      .finally(() => {
        isSubmitting.value = false;
      });
  };

  const handleReset = () => {
    tableData.value = [createRowData()];
    instanceSelectValue.value = {
      [ClusterTypes.SQLSERVER_HA]: [],
    };
    window.changeConfirm = false;
  };
</script>

<style lang="less">
  .sqlserver-slave-rebuild-original-host-box {
    padding-bottom: 20px;

    .bk-form-label {
      font-weight: bold;
      color: #313238;
    }

    .page-action-box {
      display: flex;
      align-items: center;
      margin-top: 16px;
    }

    .item-block {
      margin-top: 24px;
    }
  }
</style>
