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
  <DemandInfo
    :config="config"
    :data="ticketDetails" />
  <TargetClusterPreview
    v-model="previewTargetClusterShow"
    :cluster-ids="clusterIds"
    :title="t('目标集群预览')" />
</template>

<script setup lang="tsx">
  import { useI18n } from 'vue-i18n';

  import TicketModel, { type Mongodb } from '@services/model/ticket/ticket';

  import { TicketTypes } from '@common/const';

  import TextEllipsisOneLine from '@components/text-ellipsis-one-line/index.vue';

  import DemandInfo, {
    type DemandInfoConfig,
  } from '../components/DemandInfo.vue';

  import TargetClusterPreview from './components/TargetClusterPreview.vue';

  interface Props {
    ticketDetails: TicketModel<Mongodb.ExcelAuthorize>
  }

  type dataItem = {
    username: string,
    rule_sets: {
      db: string
      privileges: string[]
    }[],
    isExpand: boolean
  }

  const props = defineProps<Props>();

  defineOptions({
    name: TicketTypes.MONGODB_EXCEL_AUTHORIZE_RULES,
    inheritAttrs: false,
  });

  const { t } = useI18n();

  // 是否是添加授权
  const isAddAuth = props.ticketDetails.ticket_type === TicketTypes.MONGODB_AUTHORIZE_RULES;
  const ruleList = (props.ticketDetails.details?.authorize_data || [])
    .reduce((prevRuleList, authorizeItem) => [...prevRuleList, {
      username: authorizeItem.username,
      rule_sets: authorizeItem.rule_sets,
      isExpand: true,
    }], [] as dataItem[]);
  const clusterIds = props.ticketDetails.details.authorize_data?.[0].cluster_ids || [];
  const excelUrl = props.ticketDetails.details?.excel_url;

  let config: DemandInfoConfig[] = [];
  const columns = [
    {
      label: t('账号名称'),
      field: 'user',
      render: ({ data }: { data: dataItem }) => (
          <div
            class="mongo-permission-cell"
            onClick={ () => handleToggleExpand(data) }>
            {
              data.rule_sets.length > 1 && (
                <db-icon
                  type="down-shape"
                  class={[
                  'user-icon',
                  { 'user-icon-expand': data.isExpand },
                  ]} />
              )
            }
            {
              <div class="user-name">
                { data.username }
              </div>
            }
          </div>
        ),
    },
    {
      label: t('访问DB'),
      field: 'access_db',
      render: ({ data }: { data: dataItem }) => (
        getRenderList(data).map(rule => (
          <div class="mongo-permission-cell">
            <bk-tag>{ rule.db }</bk-tag>
          </div>
        ))
      ),
    },
    {
      label: t('权限'),
      field: 'privilege',
      render: ({ data }: { data: dataItem }) => (
        getRenderList(data).map(rule => (
          <div class="mongo-permission-cell">
            <TextEllipsisOneLine
              text={rule.privileges.join('，')}
              textStyle={{ color: '#63656e' }}/>
          </div>
        ))
      ),
    },
  ];

  const getConfig = () => {
    if (isAddAuth) {
      return [
        {
          list: [
            {
              label: t('目标集群'),
              render: () => (
                <>
                  <bk-button
                    text
                    theme="primary"
                    onClick={handleTargetCluster}>
                    <strong>{clusterIds.length}</strong>
                  </bk-button>
                  <span>{ t('个') }</span>
                </>
              ),
            },
            {
              label: t('权限明细'),
              isTable: true,
              render: () => (
                <db-original-table
                  class="mongo-permission-table"
                  columns={columns}
                  data={ruleList} />
              ),
            },
          ],
        },
      ];
    }

    return [
      {
        list: [
          {
            label: t('Excel文件'),
            render: () => (
              <div class="excel-link">
                <db-icon
                  color="#2dcb56"
                  svg
                  type="excel"
                  class="mr-6"/>
                <a href={excelUrl}>
                  { t('批量授权文件') }
                  <db-icon
                    class="ml-6"
                    svg
                    type="import" />
                </a>
              </div>
            ),
          },
        ],
      },
    ];
  };
  config = getConfig();

  const previewTargetClusterShow = ref(false);

  const getRenderList = (data: dataItem) => (data.isExpand ? data.rule_sets : data.rule_sets.slice(0, 1));

  const handleTargetCluster = () => {
    previewTargetClusterShow.value = true;
  };

  const handleToggleExpand = (data: dataItem) => {
    if (data.rule_sets.length <= 1) {
      return;
    }
    Object.assign(data, { isExpand: !data.isExpand });
  };
</script>

<style lang="less" scoped>
  :deep(.excel-link) {
    display: flex;
    align-items: center;
  }

  :deep(.mongo-permission-cell) {
    position: relative;
    display: flex;
    height: calc(var(--row-height) - 1px);
    padding: 0 15px;
    overflow: hidden;
    line-height: calc(var(--row-height) - 1px);
    text-align: left;
    text-overflow: ellipsis;
    white-space: nowrap;
    border-bottom: 1px solid #dcdee5;
    align-items: center;
  }

  :deep(.mongo-permission-cell:last-child) {
    border-bottom: 0;
  }

  :deep(.user-icon) {
    position: absolute;
    top: 50%;
    left: 15px;
    transform: translateY(-50%) rotate(-90deg);
    transition: all 0.2s;
  }

  :deep(.user-icon-expand) {
    transform: translateY(-50%) rotate(0);
  }

  :deep(.user-name) {
    display: flex;
    height: 100%;
    padding-left: 24px;
    font-weight: bold;
    cursor: pointer;
    align-items: center;
  }

  :deep(.mongo-permission-table) {
    transition: all 0.5s;

    td {
      .vxe-cell {
        padding: 0 !important;
      }
    }

    td:first-child {
      .cell,
      .mongo-permission-cell {
        height: 100% !important;
      }
    }
  }
</style>
