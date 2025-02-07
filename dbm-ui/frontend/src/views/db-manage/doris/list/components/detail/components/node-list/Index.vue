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
  <div class="doris-detail-node-list">
    <div class="action-box">
      <OperationBtnStatusTips :data="operationData">
        <AuthButton
          action-id="doris_scale_up"
          :disabled="operationData?.operationDisabled"
          :resource="clusterId"
          theme="primary"
          @click="handleShowExpansion">
          {{ t('扩容') }}
        </AuthButton>
      </OperationBtnStatusTips>
      <OperationBtnStatusTips :data="operationData">
        <span v-bk-tooltips="batchShrinkDisabledInfo.tooltips">
          <AuthButton
            action-id="doris_shrink"
            class="ml8"
            :disabled="batchShrinkDisabledInfo.disabled || operationData?.operationDisabled"
            :resource="clusterId"
            @click="handleShowShrink">
            {{ t('缩容') }}
          </AuthButton>
        </span>
      </OperationBtnStatusTips>
      <OperationBtnStatusTips :data="operationData">
        <span
          v-bk-tooltips="{
            content: t('请先选中节点'),
            disabled: !isBatchReplaceDisabeld,
          }">
          <AuthButton
            action-id="doris_replace"
            class="ml8"
            :disabled="isBatchReplaceDisabeld || operationData?.operationDisabled"
            :resource="clusterId"
            @click="handleShowReplace">
            {{ t('替换') }}
          </AuthButton>
        </span>
      </OperationBtnStatusTips>
      <BkDropdown
        class="ml8"
        @hide="() => (isCopyDropdown = false)"
        @show="() => (isCopyDropdown = true)">
        <BkButton>
          {{ t('复制IP') }}
          <DbIcon
            class="action-copy-icon"
            :class="{
              'action-copy-icon--avtive': isCopyDropdown,
            }"
            type="up-big" />
        </BkButton>
        <template #content>
          <BkDropdownMenu>
            <BkDropdownItem>
              <BkButton
                :disabled="tableData.length === 0"
                text
                @click="() => handleCopyIp(tableData)">
                {{ t('复制全部IP') }}
              </BkButton>
            </BkDropdownItem>
            <BkDropdownItem>
              <BkButton
                :disabled="abnormalNodeList.length === 0"
                text
                @click="() => handleCopyIp(abnormalNodeList)">
                {{ t('复制异常IP') }}
              </BkButton>
            </BkDropdownItem>
            <BkDropdownItem>
              <BkButton
                :disabled="selectedIdList.length === 0"
                text
                @click="() => handleCopyIp(Object.values(checkedNodeMap))">
                {{ t('复制已选IP') }}
              </BkButton>
            </BkDropdownItem>
          </BkDropdownMenu>
        </template>
      </BkDropdown>
      <DbSearchSelect
        class="action-box-search-select"
        :data="searchSelectData"
        :model-value="searchValue"
        :placeholder="t('请输入或选择条件搜索')"
        unique-select
        :validate-values="validateSearchValues"
        @change="handleSearchValueChange" />
    </div>
    <BkAlert
      v-if="operationData?.operationStatusText"
      class="mb16"
      theme="warning">
      <I18nT
        keypath="当前集群有xx暂时不能进行其他操作跳转xx查看进度"
        tag="div">
        <span>{{ operationData?.operationStatusText }}</span>
        <RouterLink
          target="_blank"
          :to="{
            name: 'SelfServiceMyTickets',
            query: {
              id: operationData?.operationTicketId,
            },
          }">
          {{ t('我的服务单') }}
        </RouterLink>
      </I18nT>
    </BkAlert>
    <BkLoading :loading="isLoading">
      <DbOriginalTable
        :columns="columns"
        :data="tableData"
        :is-anomalies="isAnomalies"
        :is-searching="!!searchValue.length"
        :row-class="setRowClass"
        @clear-search="clearSearchValue"
        @column-filter="columnFilterChange"
        @column-sort="columnSortChange"
        @select="handleSelect"
        @select-all="handleSelectAll" />
    </BkLoading>
    <DbSideslider
      v-model:is-show="isShowExpandsion"
      quick-close
      :title="t('xx扩容【name】', { title: 'Doris', name: operationData?.cluster_name })"
      :width="960">
      <ClusterExpansion
        v-if="operationData"
        :data="operationData"
        @change="handleOperationChange" />
    </DbSideslider>
    <DbSideslider
      v-model:is-show="isShowShrink"
      :title="t('xx缩容【name】', { title: 'Doris', name: operationData?.cluster_name })"
      :width="960">
      <ClusterShrink
        v-if="operationData"
        :data="operationData"
        :node-list="operationNodeList"
        @change="handleOperationChange" />
    </DbSideslider>
    <DbSideslider
      v-model:is-show="isShowReplace"
      :title="t('xx替换【name】', { title: 'Doris', name: operationData?.cluster_name })"
      :width="960">
      <ClusterReplace
        v-if="operationData"
        :data="operationData"
        :node-list="operationNodeList"
        @change="handleOperationChange" />
    </DbSideslider>
    <DbSideslider
      v-model:is-show="isShowDetail"
      :show-footer="false"
      :title="t('节点详情')"
      :width="960">
      <BigdataInstanceDetail
        v-if="operationNodeData"
        :cluster-id="clusterId"
        :cluster-type="ClusterTypes.DORIS"
        :data="operationNodeData"
        @close="handleClose" />
    </DbSideslider>
  </div>
</template>
<script setup lang="tsx">
  import _ from 'lodash'
  import { useI18n } from 'vue-i18n';

  import DorisDetailModel from '@services/model/doris/doris-detail';
  import DorisNodeModel from '@services/model/doris/doris-node';
  import {
    getDorisDetail,
    getDorisNodeList,
  } from '@services/source/doris';

  import {
    useCopy,
    useLinkQueryColumnSerach,
  } from '@hooks';

  import { useGlobalBizs } from '@stores';

  import { ClusterTypes } from '@common/const'

  import RenderHostStatus from '@components/render-host-status/Index.vue';
  import TextOverflowLayout from '@components/text-overflow-layout/Index.vue';

  import BigdataInstanceDetail from '@views/db-manage/common/bigdata-instance-detail/Index.vue';
  import OperationBtnStatusTips from '@views/db-manage/common/OperationBtnStatusTips.vue';
  import RenderClusterRole from '@views/db-manage/common/RenderRole.vue';
  import ClusterExpansion from '@views/db-manage/doris/common/expansion/Index.vue';
  import ClusterReplace from '@views/db-manage/doris/common/replace/Index.vue';
  import ClusterShrink from '@views/db-manage/doris/common/shrink/Index.vue';

  import { getSearchSelectorParams } from '@utils';

  import { useTimeoutPoll } from '@vueuse/core';

  interface Props {
    clusterId: number;
  }

  const props = defineProps<Props>();

  const globalBizsStore = useGlobalBizs();
  const copy = useCopy();
  const { t, locale } = useI18n();

  const {
    searchValue,
    sortValue,
    columnCheckedMap,
    columnFilterChange,
    columnSortChange,
    clearSearchValue,
    validateSearchValues,
    handleSearchValueChange,
  } = useLinkQueryColumnSerach({
    searchType: ClusterTypes.DORIS,
    attrs: ['bk_cloud_id'],
    fetchDataFn: () => fetchNodeList(),
    defaultSearchItem: {
      id: 'ip',
      name: 'IP',
    }
  });

  const searchSelectData = [
    {
      name: 'IP',
      id: 'ip',
      multiple: true,
    },
    {
      name: t('类型'),
      id: 'node_type',
      multiple: true,
      children: [
        {
          id: 'doris_backend_hot',
          name: t('热节点'),
        },
        {
          id: 'doris_backend_cold',
          name: t('冷节点'),
        },
        {
          id: 'doris_follower',
          name: 'Follower',
        },
        {
          id: 'doris_observer',
          name: 'Observer',
        },
      ],
    },
  ];

  let totalTableData: DorisNodeModel[] = [];

  const isAnomalies = ref(false);
  const isShowReplace = ref(false);
  const isShowExpandsion = ref(false);
  const isShowShrink = ref(false);
  const isShowDetail = ref(false);
  const isLoading = ref(true);
  const isCopyDropdown = ref(false);
  const operationData = shallowRef<DorisDetailModel>();
  const operationNodeData = shallowRef<DorisNodeModel>();
  const operationNodeList = shallowRef<Array<DorisNodeModel>>([]);
  const tableData = shallowRef<DorisNodeModel[]>([]);
  const checkedNodeMap = shallowRef<Record<number, DorisNodeModel>>({});

  const columns = computed(() => [
    {
      width: 60,
      fixed: 'left',
      label: () => (
        <bk-checkbox
          label={true}
          model-value={isSelectedAll.value}
          onChange={handleSelectAll}
        />
      ),
      render: ({ data }: { data: DorisNodeModel }) => (
        <bk-checkbox
          label={true}
          model-value={Boolean(checkedNodeMap.value[data.bk_host_id])}
          onChange={(value: boolean) => handleSelect(value, data)}
        />
        ),
    },
    {
      label: t('节点IP'),
      field: 'ip',
      width: 140,
      showOverflowTooltip: false,
      render: ({ data }: { data: DorisNodeModel }) => (
        <TextOverflowLayout>
          {{
            default: () => <span>{data.ip}</span>,
            append: () => (
              <>
                {
                  data.isNew && (
                    <bk-tag
                      theme="success"
                      size="small"
                      class="ml-4">
                      NEW
                    </bk-tag>
                  )
                }
              </>
            )
          }}
        </TextOverflowLayout>
      ),
    },
    {
      label: t('实例数量'),
      field: 'node_count',
      sort: true,
      width: 120,
    },
    {
      label: t('类型'),
      field: 'node_type',
      filter: {
        filterFn: () => true,
        list: [
          {
            value: 'doris_backend_hot',
            text: t('热节点'),
          },
          {
            value: 'doris_backend_cold',
            text: t('冷节点'),
          },
          {
            value: 'doris_follower',
            text: 'Follower',
          },
          {
            value: 'doris_observer',
            text: 'Observer',
          },
        ],
        checked: columnCheckedMap.value.node_type,
      },
      width: 200,
      render: ({ data }: { data: DorisNodeModel }) => <RenderClusterRole data={[data.role]} />,
    },
    {
      label: t('Agent状态'),
      field: 'status',
      width: 120,
      render: ({ data }: { data: DorisNodeModel }) => <RenderHostStatus data={data.status} />,
    },
    {
      label: t('部署时间'),
      field: 'create_at',
      sort: true,
      render: ({ data }: { data: DorisNodeModel }) => <span>{data.createAtDisplay}</span>,
    },
    {
      label: t('操作'),
      width: isCN.value ? 200 : 260,
      fixed: 'right',
      render: ({ data }: { data: DorisNodeModel }) => {
        const shrinkDisableTooltips = checkNodeShrinkDisable(data);
        return (
          <>
            <OperationBtnStatusTips data={operationData.value}>
              <span v-bk-tooltips={shrinkDisableTooltips.tooltips}>
                <auth-button
                  text
                  theme="primary"
                  action-id="doris_shrink"
                  permission={data.permission.doris_shrink}
                  resource={data.bk_host_id}
                  disabled={
                    shrinkDisableTooltips.disabled
                    || operationData.value?.operationDisabled
                  }
                  onClick={() => handleShrinkOne(data)}>
                  {t('缩容')}
                </auth-button>
              </span>
            </OperationBtnStatusTips>
            <OperationBtnStatusTips data={operationData.value}>
              <auth-button
                text
                theme="primary"
                action-id="doris_replace"
                permission={data.permission.doris_replace}
                resource={data.bk_host_id}
                class="ml-8"
                disabled={operationData.value?.operationDisabled}
                onClick={() => handleReplaceOne(data)}>
                {t('替换')}
              </auth-button>
            </OperationBtnStatusTips>
            <OperationBtnStatusTips data={operationData.value}>
              <auth-button
                text
                theme="primary"
                action-id="doris_reboot"
                permission={data.permission.doris_reboot}
                resource={data.bk_host_id}
                class="ml-8"
                disabled={operationData.value?.operationDisabled}
                onClick={() => handleShowDetail(data)}>
                {t('重启实例')}
              </auth-button>
            </OperationBtnStatusTips>
          </>
        );
      },
    },
  ]);

  const isCN = computed(() => locale.value === 'zh-cn');
  const isSelectedAll = computed(() => tableData.value.length > 0
    && Object.keys(checkedNodeMap.value).length >= tableData.value.length);

  const batchShrinkDisabledInfo = computed(() => {
    // 1.Follower 为必须，3个节点, 缩容
    // 2.Observer 非必选，若选至少需要2台
    // 3.冷/热 数据节点必选1种以上，每个角色至少需要2台

    const options = {
      disabled: false,
      tooltips: {
        disabled: true,
        content: '',
      },
    };
    const selectList = Object.values(checkedNodeMap.value);
    if (selectList.length < 1) {
      options.disabled = true;
      options.tooltips.disabled = false;
      options.tooltips.content = t('请先选中节点');
      return options;
    }
    if (selectList.some(item => item.isFollower)) {
      options.disabled = true;
      options.tooltips.disabled = false;
      options.tooltips.content = t('Follower节点不支持缩容');
      return options;
    }

    let observerNumTotal = 0;
    let observerNum = 0
    let hotNodeNumTotal = 0;
    let hotNodeNum = 0;
    let coldNodeNumTotal = 0;
    let coldNodeNum = 0;
    totalTableData.forEach((nodeItem) => {
      if (nodeItem.isObserver) {
        observerNumTotal = observerNumTotal + 1;
      } else if (nodeItem.isHot) {
        hotNodeNumTotal = hotNodeNumTotal + 1;
      } else if (nodeItem.isCold) {
        coldNodeNumTotal = coldNodeNumTotal + 1;
      }
      if (checkedNodeMap.value[nodeItem.bk_host_id]) {
        return;
      }
      if (nodeItem.isObserver) {
        observerNum = observerNum + 1;
      } else if (nodeItem.isHot) {
        hotNodeNum = hotNodeNum + 1;
      } else if (nodeItem.isCold) {
        coldNodeNum = coldNodeNum + 1;
      }
    });

    if (observerNumTotal > 0 && (observerNumTotal - observerNum === 1)) {
      options.disabled = true;
      options.tooltips.disabled = false;
      options.tooltips.content = t('Observer类型节点若存在至少保留两台');
    } else if ((hotNodeNumTotal === 0 && coldNodeNum === 1) || (coldNodeNumTotal === 0 && hotNodeNum === 1)) {
      options.disabled = true;
      options.tooltips.disabled = false;
      options.tooltips.content = t('冷/热 数据节点必选 1 种以上，每个角色至少需要 2 台');
    }

    return options;
  });

  const isBatchReplaceDisabeld = computed(() => Object.keys(checkedNodeMap.value).length < 1);
  const selectedIdList = computed(() => Object.values(checkedNodeMap.value).map(item => item.ip));
  const abnormalNodeList = computed(() => tableData.value.filter(item => item.isAbnormal));

  const fetchClusterDetail = () => {
    // 获取集群详情
    getDorisDetail({
      id: props.clusterId,
    })
      .then((data) => {
        operationData.value = data;
      });
  };

  const {
    pause: pauseFetchClusterDetail,
    resume: resumeFetchClusterDetail,
  } = useTimeoutPoll(fetchClusterDetail, 2000, {
    immediate: true,
  });

  const fetchNodeList = () => {
    isLoading.value = true;
    const extraParams = {
      ...getSearchSelectorParams(searchValue.value),
      ...sortValue,
    };
    getDorisNodeList({
      bk_biz_id: globalBizsStore.currentBizId,
      cluster_id: props.clusterId,
      no_limit: 1,
      ...extraParams,
    })
      .then((data) => {
        tableData.value = data.results;
        isAnomalies.value = false;
        if (searchValue.value.length === 0) {
          totalTableData = _.cloneDeep(tableData.value);
        }
      })
      .catch(() => {
        tableData.value = [];
        isAnomalies.value = true;
      })
      .finally(() => {
        isLoading.value = false;
      });
  };

  watch(() => props.clusterId, () => {
    pauseFetchClusterDetail();
    resumeFetchClusterDetail();
    fetchNodeList();
  }, {
    immediate: true,
  });

  const setRowClass = (data: DorisNodeModel) => (data.isNew ? 'is-new-row' : '');

  const checkNodeShrinkDisable = (node: DorisNodeModel) => {
    const options = {
      disabled: false,
      tooltips: {
        disabled: true,
        content: '',
      },
    };

    // follower 节点不支持缩容
    if (node.isFollower) {
      options.disabled = true;
      options.tooltips.disabled = false;
      options.tooltips.content = t('节点类型不支持缩容');
    } else {
      // Observer 若存在至少需要2台
      // 冷/热 数据节点必选1种以上，每个角色至少需要2台
      let observerNodeNum = 0;
      let hotNodeNum = 0;
      let coldNodeNum = 0;
      tableData.value.forEach((nodeItem) => {
        if (nodeItem.isObserver) {
          observerNodeNum = observerNodeNum + 1;
        } else if (nodeItem.isHot) {
          hotNodeNum = hotNodeNum + 1;
        } else if (nodeItem.isCold) {
          coldNodeNum = coldNodeNum + 1;
        }
      });

      if (node.isObserver && observerNodeNum === 2) {
        options.disabled = true;
        options.tooltips.disabled = false;
        options.tooltips.content = t('Follower类型节点若存在至少保留两台');
      } else if (node.isHot && hotNodeNum > 0  && coldNodeNum === 0) {
        options.disabled = true;
        options.tooltips.disabled = false;
        options.tooltips.content = t('冷/热 数据节点必选 1 种以上，每个角色至少需要 2 台');
      } else if (node.isCold && coldNodeNum > 0  && hotNodeNum === 0) {
        options.disabled = true;
        options.tooltips.disabled = false;
        options.tooltips.content = t('冷/热 数据节点必选 1 种以上，每个角色至少需要 2 台');
      }
    }

    return options;
  };

  const handleOperationChange = () => {
    fetchNodeList();
    checkedNodeMap.value = {};
  };

  // 扩容
  const handleShowExpansion = () => {
    isShowExpandsion.value = true;
  };

  // 复制IP
  const handleCopyIp = (dataList: DorisNodeModel[]) => {
    const ipList = dataList.map(nodeItem => nodeItem.ip);
    copy(ipList.join('\n'));
  };

  const handleSelect = (checked: boolean, data: DorisNodeModel) => {
    const checkedMap = { ...checkedNodeMap.value };
    if (checked) {
      checkedMap[data.bk_host_id] = new DorisNodeModel(data);
    } else {
      delete checkedMap[data.bk_host_id];
    }

    checkedNodeMap.value = checkedMap;
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      checkedNodeMap.value = tableData.value.reduce((result, nodeData) => ({
        ...result,
        [nodeData.bk_host_id]: nodeData,
      }), {} as Record<number, DorisNodeModel>);
    } else {
      checkedNodeMap.value = {};
    }
  };

  // 批量缩容
  const handleShowShrink = () => {
    operationNodeList.value = Object.values(checkedNodeMap.value);
    isShowShrink.value = true;
  };

  // 批量扩容
  const handleShowReplace = () => {
    operationNodeList.value = Object.values(checkedNodeMap.value);
    isShowReplace.value = true;
  };
  const handleShrinkOne = (data: DorisNodeModel) => {
    operationNodeList.value = [data];
    isShowShrink.value = true;
  };

  const handleReplaceOne = (data: DorisNodeModel) => {
    operationNodeList.value = [data];
    isShowReplace.value = true;
  };

  const handleShowDetail = (data: DorisNodeModel) => {
    isShowDetail.value = true;
    operationNodeData.value = data;
  };

  const handleClose = () => {
    isShowDetail.value = false;
  };
</script>

<style lang="less" scoped>
  .doris-detail-node-list {
    padding: 16px 0;

    .action-box {
      display: flex;
      margin-bottom: 16px;

      .action-box-search-select {
        max-width: 360px;
        margin-left: auto;
        flex: 1;
      }
    }

    .action-copy-icon {
      margin-left: 6px;
      color: #979ba5;
      transform: rotateZ(180deg);
      transition: all 0.2s;

      &--avtive {
        transform: rotateZ(0);
      }
    }
  }
</style>

<style lang="less">
  .doris-breadcrumbs-box {
    display: flex;
    width: 100%;
    margin-left: 8px;
    font-size: 12px;
    align-items: center;

    .doris-breadcrumbs-box-status {
      display: flex;
      margin-left: 30px;
      align-items: center;
    }

    .doris-breadcrumbs-box-button {
      display: flex;
      margin-left: auto;
      align-items: center;

      .more-button {
        padding: 3px 6px;
      }
    }
  }
</style>
