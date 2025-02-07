<template>
  <BkResizeLayout
    class="quick-search"
    collapsible
    :initial-divide="320"
    :max="500"
    :min="300"
    placement="right"
    style="height: 100%">
    <template #main>
      <div class="quick-search-head">
        <div class="quick-search-search">
          <SearchInput
            v-model="keyword"
            v-model:filter-type="formData.filter_type"
            @search="handleSearch" />
        </div>
        <BkTab
          v-model:active="activeTab"
          class="quick-search-tab"
          type="unborder-card">
          <BkTabPanel
            v-for="item in panelList"
            :key="item.name"
            :label="item.label"
            :name="item.name">
            <template #label>
              <div>{{ item.label }} ( {{ item.count }} )</div>
            </template>
          </BkTabPanel>
        </BkTab>
        <div class="tab-content">
          <BkLoading
            class="tab-content-loading"
            :loading="loading">
            <ScrollFaker>
              <KeepAlive>
                <Component
                  :is="renderComponent"
                  :biz-id-name-map="bizIdNameMap"
                  class="tab-table"
                  :data="dataList"
                  :is-anomalies="!!error"
                  :is-searching="isSearching"
                  :keyword="keyword"
                  @clear-search="handleClearSearch"
                  @refresh="handleSearch" />
              </KeepAlive>
            </ScrollFaker>
          </BkLoading>
        </div>
      </div>
    </template>
    <template #aside>
      <ScrollFaker class="tab-filter-options">
        <FilterOptions
          v-model="formData"
          :biz-list="bizList"
          db-options-expand />
      </ScrollFaker>
    </template>
  </BkResizeLayout>
</template>

<script setup lang="ts">
  import { useI18n } from 'vue-i18n';
  import { useRequest } from 'vue-request';

  import { quickSearch } from '@services/source/quickSearch';

  import { useUrlSearch } from '@hooks';

  import { useGlobalBizs } from '@stores';

  import { batchSplitRegex } from '@common/regex';

  import { FilterType } from '@components/system-search/components/FilterTypeSelect.vue';
  import FilterOptions from '@components/system-search/components/search-result/FilterOptions.vue';

  import Entry from './components/Entry.vue';
  import Instance from './components/Instance.vue';
  import ResourcePool from './components/ResourcePool.vue';
  import SearchInput from './components/SearchInput.vue';
  import Task from './components/Task.vue';
  import Ticket from './components/Ticket.vue';

  type MapArrayToString<T> = {
    [K in keyof T]: T[K] extends Array<string | number> ? string : T[K];
  };

  const route = useRoute();
  const router = useRouter();
  const { t } = useI18n();
  const { bizs: bizList } = useGlobalBizs();
  const { getSearchParams, replaceSearchParams } = useUrlSearch();

  let isRedirectSearch = true;
  let routeParamsMemo = {};

  const comMap = {
    entry: Entry,
    instance: Instance,
    task: Task,
    resource_pool: ResourcePool,
    ticket: Ticket,
  };

  const bizIdNameMap = bizList.reduce(
    (result, item) => Object.assign(result, { [item.bk_biz_id]: item.name }),
    {} as Record<number, string>,
  );

  // const keyword = ref((route.query.keyword as string) || '');
  const keyword = ref('');
  const dataMap = ref<Omit<ServiceReturnType<typeof quickSearch>, 'keyword' | 'short_code'>>({
    entry: [],
    instance: [],
    task: [],
    resource_pool: [],
    ticket: [],
  });

  const formData = ref({
    bk_biz_ids: [] as number[],
    db_types: [] as string[],
    resource_types: [] as string[],
    filter_type: FilterType.EXACT,
  });
  const activeTab = ref('entry');
  const panelList = reactive([
    {
      name: 'entry',
      label: t('访问入口'),
      count: 0,
    },
    {
      name: 'instance',
      label: t('实例（IP、IP:Port）'),
      count: 0,
    },
    {
      name: 'task',
      label: t('历史任务'),
      count: 0,
    },
    {
      name: 'ticket',
      label: t('单据'),
      count: 0,
    },
    {
      name: 'resource_pool',
      label: t('主机（资源池、故障池、待回收池）'),
      count: 0,
    },
  ]);

  const isSearching = computed(() => loading.value && !!keyword.value);

  const renderComponent = computed(() => {
    if (loading.value) {
      return null;
    }

    const activeComponent = comMap[activeTab.value as keyof typeof comMap];

    if (activeComponent) {
      return activeComponent;
    }
    return Entry;
  });

  const dataList = computed(() => {
    if (loading.value) {
      return [];
    }
    const activeDataList = dataMap.value[activeTab.value as keyof typeof comMap];
    if (activeDataList) {
      return activeDataList;
    }
    return dataMap.value.entry;
  });

  const {
    loading,
    error,
    run: quickSearchRun,
  } = useRequest(quickSearch, {
    manual: true,
    onSuccess(data, params) {
      if (isRedirectSearch) {
        keyword.value = data.keyword.replace(batchSplitRegex, '|');
        handleSearch();
      }
      Object.assign(dataMap.value, {
        entry: data.entry,
        instance: data.instance,
        task: data.task,
        resource_pool: data.resource_pool,
        ticket: data.ticket,
      });
      panelList[0].count = data.entry.length;
      panelList[1].count = data.instance.length;
      panelList[2].count = data.task.length;
      panelList[3].count = data.ticket.length;
      panelList[4].count = data.resource_pool.length;

      const panelItem = panelList.find((panel) => panel.count > 0);
      if (panelItem) {
        activeTab.value = panelItem.name;
      }

      const serachParams = Object.entries(params[0]).reduce<Record<string, MapArrayToString<(typeof params)[0]>>>(
        (prev, [key, value]) => {
          if (Array.isArray(value)) {
            return Object.assign(prev, { [key]: value.join(',') });
          }
          return Object.assign(prev, { [key]: value });
        },
        {},
      );
      Object.assign(serachParams, {
        short_code: data.short_code,
      });
      delete serachParams.keyword;
      routeParamsMemo = {
        ...routeParamsMemo,
        ...serachParams,
      };

      replaceSearchParams(routeParamsMemo);
    },
    onAfter() {
      isRedirectSearch = false;
    },
  });

  watch(
    formData,
    () => {
      handleSearch();
    },
    {
      deep: true,
    },
  );

  const clearData = () => {
    Object.assign(dataMap.value, {
      entry: [],
      instance: [],
      task: [],
      resource_pool: [],
      ticket: [],
    });
    panelList[0].count = 0;
    panelList[1].count = 0;
    panelList[2].count = 0;
    panelList[3].count = 0;
    panelList[4].count = 0;
  };

  const handleSearch = () => {
    if (!keyword.value) {
      clearData();
      return;
    }

    quickSearchRun({
      ...formData.value,
      keyword: keyword.value.replace(batchSplitRegex, ' '),
      limit: 1000,
    });
  };

  // watch(
  //   keyword,
  //   (newKeyword, oldKeyword) => {
  //     const newKeywordArr = newKeyword.split(batchSplitRegex);
  //     const oldKeywordArr = (oldKeyword || '').split(batchSplitRegex);

  //     if (!_.isEqual(newKeywordArr, oldKeywordArr) && !newKeyword.endsWith('\n')) {
  //       handleSearch();
  //     }
  //   },
  //   {
  //     immediate: true,
  //   },
  // );

  watch(
    formData,
    () => {
      handleSearch();
    },
    {
      deep: true,
    },
  );

  // const handleExportAllClusters = () => {

  // };

  // const handleExportAllHosts = () => {

  // };

  const handleClearSearch = () => {
    keyword.value = '';
  };

  // 初始化查询
  const initRetrieve = () => {
    const formatRouteQuery = (initParams: Record<string, string>) => {
      const {
        filter_type: filterType,
        bk_biz_ids: bkBizIds,
        db_types: dbTypes,
        resource_types: resourceTypes,
      } = initParams;

      return {
        bk_biz_ids: bkBizIds ? bkBizIds.split(',').map((bizId) => Number(bizId)) : [],
        db_types: dbTypes ? dbTypes.split(',') : [],
        resource_types: resourceTypes ? resourceTypes.split(',') : [],
        filter_type: (filterType as FilterType) || FilterType.EXACT,
      };
    };
    const initParams = getSearchParams();
    routeParamsMemo = initParams;
    formData.value = formatRouteQuery(initParams);
    const shortCode = initParams?.short_code || initParams?.keyword;
    if (shortCode) {
      quickSearchRun({
        ...formData.value,
        short_code: shortCode,
        limit: 1000,
      });
    }
  };
  initRetrieve();

  defineExpose({
    routerBack() {
      if (!route.query.from) {
        router.back();
        return;
      }
      router.push({
        name: route.query.from as string,
      });
    },
  });
</script>

<style lang="less" scoped>
  .quick-search {
    height: 100%;

    .quick-search-head {
      height: 100%;
      background-color: #fff;

      .quick-search-search {
        display: flex;
        padding: 45px 0 32px;
        justify-content: center;

        .export-button {
          height: 40px;

          .export-icon {
            font-size: 16px;
          }
        }
      }

      .quick-search-tab {
        box-shadow: 0 2px 4px 0 #1919290d;

        :deep(.bk-tab-header) {
          justify-content: center;
          border-bottom: none;
        }

        :deep(.bk-tab-content) {
          padding: 0 !important;
        }
      }

      .tab-content {
        height: calc(100% - 162px);
        background-color: #f5f7fa;

        :deep(.tab-content-loading) {
          height: 100%;
          padding: 16px 0;

          .bk-loading-mask {
            z-index: 3 !important;
          }

          .bk-loading-indicator {
            z-index: 3 !important;
          }
        }

        .tab-table {
          margin: 0 24px;
        }
      }
    }

    .tab-filter-options {
      padding: 10px 12px;
      background-color: #fff;
    }

    :deep(.bk-resize-collapse) {
      z-index: 3;
    }
  }
</style>
