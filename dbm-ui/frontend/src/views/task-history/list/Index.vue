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
  <div class="task-history-list-page">
    <div class="header-action">
      <DbSearchSelect
        :data="searchData"
        :get-menu-list="getMenuList"
        :model-value="searchValue"
        :placeholder="t('ID_任务类型_状态_关联单据')"
        style="width: 500px"
        @change="handleSearchValueChange" />
      <BkDatePicker
        v-model="state.filter.daterange"
        class="ml-8"
        :placeholder="t('选择日期范围')"
        style="width: 300px"
        type="daterange"
        @change="fetchTableData" />
    </div>
    <DbTable
      ref="tableRef"
      :data-source="dataSource"
      @clear-search="handleClearSearch"
      @column-filter="columnFilterChange">
      <BkTableColumn
        field="root_id"
        fixed="left"
        label="ID"
        :min-width="120">
        <template #default="{data}: {data: TaskFlowModel}">
          <AuthButton
            action-id="flow_detail"
            :permission="data.permission.flow_detail"
            :resource="data.root_id"
            text
            theme="primary"
            @click="handleGoDetail(data)">
            {{ data.root_id }}
          </AuthButton>
        </template>
      </BkTableColumn>
      <BkTableColumn
        field="bk_biz_name"
        :label="t('业务')"
        :width="150" />
      <BkTableColumn
        field="ticket_type"
        :filterss="{
          list: state.ticketTypes.map((item) => ({
            label: item.name,
            value: item.id,
          })),
          checked: columnCheckedMap.ticket_type,
        }"
        :label="t('任务类型')">
        <template #default="{data}: {data: TaskFlowModel}">
          {{ data.ticket_type_display || '--' }}
        </template>
      </BkTableColumn>
      <BkTableColumn
        field="status"
        :filterss="{
          list: Object.keys(TaskFlowModel.STATUS_TEXT_MAP).map((id) => ({
            label: t(TaskFlowModel.STATUS_TEXT_MAP[id]),
            value: id,
          })),
          checked: columnCheckedMap.status,
        }"
        :label="t('状态')"
        :width="160">
        <template #default="{data}: {data: TaskFlowModel}">
          <DbStatus
            :theme="data.statusTheme"
            type="linear">
            {{ t(data.statusText) }}
          </DbStatus>
        </template>
      </BkTableColumn>
      <BkTableColumn
        field="uid"
        :label="t('关联单据')"
        :width="100">
        <template #default="{data}: {data: TaskFlowModel}">
          <AuthButton
            v-if="data.uid"
            action-id="ticket_view"
            :permission="data.permission.ticket_view"
            :resource="data.uid"
            text
            theme="primary"
            @click="handleGoTicketDetail(data)">
            {{ data.uid }}
          </AuthButton>
          <span v-else>--</span>
        </template>
      </BkTableColumn>
      <BkTableColumn
        field="created_by"
        :label="t('执行人')"
        :width="120">
        <template #default="{data}: {data: TaskFlowModel}">
          {{ data.created_by }}
        </template>
      </BkTableColumn>
      <BkTableColumn
        field="created_at"
        :label="t('执行时间')"
        :width="250">
        <template #default="{data}: {data: TaskFlowModel}">
          {{ data.createAtDisplay }}
        </template>
      </BkTableColumn>
      <BkTableColumn
        field="cost_time"
        :label="t('耗时')"
        :width="150">
        <template #default="{data}: {data: TaskFlowModel}">
          {{ getCostTimeDisplay(data.cost_time) }}
        </template>
      </BkTableColumn>
      <BkTableColumn
        :label="t('操作')"
        :width="120">
        <template #default="{data}: {data: TaskFlowModel}">
          <AuthButton
            action-id="flow_detail"
            :permission="data.permission.flow_detail"
            :resource="data.root_id"
            text
            theme="primary"
            @click="handleGoDetail(data)">
            {{ t('查看详情') }}
          </AuthButton>
          <BkButton
            v-if="includesResultFiles.includes(data.ticket_type) && data.status === 'FINISHED'"
            class="ml-6"
            text
            theme="primary"
            @click="handleShowResultFiles(data.root_id)">
            {{ t('查看结果文件') }}
          </BkButton>
        </template>
      </BkTableColumn>
    </DbTable>
  </div>
  <!-- 结果文件功能 -->
  <RedisResultFiles
    :id="resultFileState.rootId"
    v-model="resultFileState.isShow" />
</template>

<script setup lang="tsx">
  import type { ISearchItem } from 'bkui-vue/lib/search-select/utils';
  import { format } from 'date-fns';
  import { useI18n } from 'vue-i18n';
  import { useRequest } from 'vue-request';
  import { useRoute, useRouter } from 'vue-router';

  import TaskFlowModel from '@services/model/taskflow/taskflow';
  import { getTaskflow } from '@services/source/taskflow';
  import { getTicketTypes } from '@services/source/ticket';
  import { getUserList } from '@services/source/user';

  import { useLinkQueryColumnSerach } from '@hooks';

  import { TicketTypes, type TicketTypesStrings } from '@common/const';
  import { ClusterTypes } from '@common/const';

  import DbStatus from '@components/db-status/index.vue';

  import { getBusinessHref, getCostTimeDisplay, getMenuListSearch, getSearchSelectorParams } from '@utils';

  import type { ListState } from '../common/types';
  import RedisResultFiles from '../components/RedisResultFiles.vue';

  const router = useRouter();
  const route = useRoute();
  const { t } = useI18n();

  const isPlatformManage = route.name === 'platformTaskHistoryList';

  const dataSource = (params: Parameters<typeof getTaskflow>[0]) =>
    getTaskflow({
      ...params,
      bk_biz_id: isPlatformManage ? undefined : window.PROJECT_CONFIG.BIZ_ID,
    });

  const { searchValue, columnCheckedMap, columnFilterChange, clearSearchValue, handleSearchValueChange } =
    useLinkQueryColumnSerach({
      searchType: ClusterTypes.TENDBHA,
      attrs: [],
      fetchDataFn: () => fetchTableData(),
      isCluster: false,
      isQueryAttrs: false,
    });

  /**
   * 近 7 天
   */
  const initDate = () => {
    const end = new Date();
    const start = new Date();
    start.setTime(start.getTime() - 3600 * 1000 * 24 * 7);
    return [start.toISOString(), end.toISOString()] as [string, string];
  };

  // 可查看结果文件类型
  const includesResultFiles: TicketTypesStrings[] = [TicketTypes.REDIS_KEYS_EXTRACT, TicketTypes.REDIS_KEYS_DELETE];

  const tableRef = ref();
  const state = reactive<ListState>({
    data: [],
    ticketTypes: [],
    filter: {
      daterange: initDate(),
    },
  });
  /** 查看结果文件功能 */
  const resultFileState = reactive({
    isShow: false,
    rootId: '',
  });

  const searchData = computed(() => [
    {
      name: 'ID',
      id: 'root_ids',
    },
    {
      name: t('任务类型'),
      id: 'ticket_type',
      multiple: true,
      children: state.ticketTypes,
    },
    {
      name: t('状态'),
      id: 'status',
      multiple: true,
      children: Object.keys(TaskFlowModel.STATUS_TEXT_MAP).map((id: string) => ({
        id,
        name: t(TaskFlowModel.STATUS_TEXT_MAP[id]),
      })),
    },
    {
      name: t('关联单据'),
      id: 'uid',
    },
    {
      name: t('执行人'),
      id: 'created_by',
    },
  ]);

  useRequest(getTicketTypes, {
    onSuccess(data) {
      state.ticketTypes = data.map((item) => ({
        id: item.key,
        name: item.value,
      }));
    },
  });

  const fetchTableData = () => {
    const { daterange } = state.filter;
    const dateParams =
      daterange.filter((item) => item).length === 0
        ? {}
        : {
            created_at__gte: format(new Date(daterange[0]), 'yyyy-MM-dd HH:mm:ss'),
            created_at__lte: format(new Date(daterange[1]), 'yyyy-MM-dd HH:mm:ss'),
          };

    tableRef.value.fetchData({
      ...dateParams,
      ...getSearchSelectorParams(searchValue.value),
    });
  };

  async function getMenuList(item: ISearchItem | undefined, keyword: string) {
    if (item?.id !== 'created_by' && keyword) {
      return getMenuListSearch(item, keyword, searchData.value, searchValue.value);
    }

    // 没有选中过滤标签
    if (!item) {
      // 过滤掉已经选过的标签
      const selected = (searchValue.value || []).map((value) => value.id);
      return searchData.value.filter((item) => !selected.includes(item.id));
    }

    // 远程加载执行人
    if (item.id === 'created_by') {
      if (!keyword) {
        return [];
      }
      return getUserList({
        fuzzy_lookups: keyword,
      }).then((res) =>
        res.results.map((item) => ({
          id: item.username,
          name: item.username,
        })),
      );
    }

    // 不需要远层加载
    return searchData.value.find((set) => set.id === item.id)?.children || [];
  }

  const handleClearSearch = () => {
    state.filter.daterange = ['', ''];
    clearSearchValue();
  };

  const handleShowResultFiles = (id: string) => {
    resultFileState.isShow = true;
    resultFileState.rootId = id;
  };

  const handleGoDetail = (data: TaskFlowModel) => {
    const { href } = router.resolve({
      name: 'taskHistoryDetail',
      params: {
        root_id: data.root_id,
      },
      query: {
        from: route.name as string,
      },
    });

    window.open(getBusinessHref(href), '_blank');
  };

  const handleGoTicketDetail = (data: TaskFlowModel) => {
    const { href } = router.resolve({
      name: 'bizTicketManage',
      params: {
        ticketId: data.uid,
      },
    });

    window.open(getBusinessHref(href), '_blank');
  };
</script>

<style lang="less">
  .task-history-list-page {
    .header-action {
      display: flex;
      padding-bottom: 16px;
    }
  }
</style>
