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
  <Teleport to="#dbContentHeaderAppend">
    <div
      v-if="isStretchLayoutOpen && data"
      class="replica-set-breadcrumbs-box">
      <BkTag>{{ data.cluster_name }}</BkTag>
      <div class="replica-set-breadcrumbs-box-status">
        <span>{{ t('状态') }} :</span>
        <RenderClusterStatus
          class="ml-8"
          :data="data.status" />
      </div>
      <div class="replica-set-breadcrumbs-box-button">
        <BkButton
          :disabled="data.isOffline"
          size="small"
          @click="handleShowAccessEntry">
          {{ t('获取访问方式') }}
        </BkButton>
        <BkButton
          class="ml-4"
          size="small"
          @click="handleCapacityChange">
          {{ t('集群容量变更') }}
        </BkButton>
        <BkDropdown class="ml-4">
          <BkButton
            class="more-button"
            size="small">
            <DbIcon type="more" />
          </BkButton>
          <template #content>
            <BkDropdownMenu>
              <BkDropdownItem>
                <BkButton
                  :disabled="Boolean(data.operationTicketId)"
                  text
                  @click="handleDisableCluster([data])">
                  {{ t('禁用集群') }}
                </BkButton>
              </BkDropdownItem>
            </BkDropdownMenu>
          </template>
        </BkDropdown>
      </div>
    </div>
  </Teleport>
  <div
    v-bkloading="{ loading: isLoading }"
    class="cluster-details">
    <BkTab
      v-model:active="activePanelKey"
      class="content-tabs"
      type="card-tab">
      <BkTabPanel
        v-if="checkDbConsole('mongodb.replicaSetList.clusterTopo')"
        :label="t('集群拓扑')"
        name="topo" />
      <BkTabPanel
        v-if="checkDbConsole('mongodb.replicaSetList.basicInfo')"
        :label="t('基本信息')"
        name="info" />
      <BkTabPanel
        v-if="checkDbConsole('mongodb.replicaSetList.changeLog')"
        :label="t('变更记录')"
        name="record" />
      <BkTabPanel
        v-for="item in monitorPanelList"
        :key="item.name"
        :label="item.label"
        :name="item.name" />
    </BkTab>
    <div class="content-wrapper">
      <ClusterTopo
        v-if="activePanelKey === 'topo'"
        :id="clusterId"
        :cluster-type="ClusterTypes.MONGODB"
        :db-type="DBTypes.MONGODB" />
      <BaseInfo
        v-if="activePanelKey === 'info' && data"
        :data="data" />
      <ClusterEventChange
        v-if="activePanelKey === 'record'"
        :id="clusterId" />
      <MonitorDashboard
        v-if="activePanelKey === activePanel?.name"
        :url="activePanel?.link" />
    </div>
    <DbSideslider
      v-if="capacityData"
      v-model:is-show="capacityChangeShow"
      :disabled-confirm="!isCapacityChange"
      :width="960">
      <template #header>
        <span>
          {{ t('MongoDB 集群容量变更【xxx】', [capacityData.clusterName]) }}
          <BkTag theme="info">
            {{ t('存储层') }}
          </BkTag>
        </span>
      </template>
      <CapacityChange
        v-model:is-change="isCapacityChange"
        :data="capacityData" />
    </DbSideslider>
    <AccessEntry
      v-if="accessEntryInfo"
      v-model:is-show="accessEntryInfoShow"
      :data="accessEntryInfo" />
  </div>
</template>

<script setup lang="ts">
  import { useI18n } from 'vue-i18n';
  import { useRequest } from 'vue-request';

  import MongodbDetailModel from '@services/model/mongodb/mongodb-detail';
  import { getMongoClusterDetails } from '@services/source/mongodb';
  import { getMonitorUrls } from '@services/source/monitorGrafana';

  import { useStretchLayout } from '@hooks';

  import { useGlobalBizs } from '@stores';

  import { ClusterTypes, DBTypes } from '@common/const';

  import RenderClusterStatus from '@components/cluster-status/Index.vue';

  import ClusterTopo from '@views/db-manage/common/cluster-details/ClusterTopo.vue';
  import ClusterEventChange from '@views/db-manage/common/cluster-event-change/EventChange.vue';
  import MonitorDashboard from '@views/db-manage/common/cluster-monitor/MonitorDashboard.vue';
  import { useOperateClusterBasic } from '@views/db-manage/common/hooks';
  import AccessEntry from '@views/db-manage/mongodb/components/AccessEntry.vue';
  import CapacityChange from '@views/db-manage/mongodb/components/CapacityChange.vue';

  import { checkDbConsole } from '@utils';

  import BaseInfo from './BaseInfo.vue';

  interface Props {
    clusterId: number;
  }

  const props = defineProps<Props>();

  const { t } = useI18n();
  const { currentBizId } = useGlobalBizs();
  const { isOpen: isStretchLayoutOpen } = useStretchLayout();
  const { handleDisableCluster } = useOperateClusterBasic(ClusterTypes.MONGODB, {
    onSuccess: () => fetchResourceDetails({ cluster_id: props.clusterId }),
  });

  const activePanelKey = ref('topo');
  const capacityChangeShow = ref(false);
  const isCapacityChange = ref(false);
  const capacityData = ref<{
    id: number;
    clusterName: string;
    specId: number;
    specName: string;
    bizId: number;
    cloudId: number;
    shardNum: number;
    shardNodeCount: number;
  }>();
  const monitorPanelList = ref<
    {
      label: string;
      name: string;
      link: string;
    }[]
  >([]);
  const accessEntryInfoShow = ref(false);
  const accessEntryInfo = ref<MongodbDetailModel | undefined>();

  const activePanel = computed(() => monitorPanelList.value.find((item) => item.name === activePanelKey.value));

  const {
    data,
    loading: isLoading,
    run: fetchResourceDetails,
  } = useRequest(getMongoClusterDetails, {
    manual: true,
    onSuccess(result) {
      const {
        id,
        cluster_name: clusterName,
        bk_biz_id: bizId,
        bk_cloud_id: cloudId,
        shard_num: shardNum,
        shard_node_count: shardNodeCount,
        mongodb,
      } = result;
      const { id: specId, name } = mongodb[0].spec_config;

      capacityData.value = {
        id,
        clusterName,
        specId,
        specName: name,
        bizId,
        cloudId,
        shardNum,
        shardNodeCount,
      };
      accessEntryInfo.value = result;
    },
  });

  const { run: runGetMonitorUrls } = useRequest(getMonitorUrls, {
    manual: true,
    onSuccess(res) {
      if (res.urls.length > 0) {
        monitorPanelList.value = res.urls.map((item) => ({
          label: item.view,
          name: item.view,
          link: item.url,
        }));
      }
    },
  });

  watch(
    () => props.clusterId,
    () => {
      if (!props.clusterId) {
        return;
      }
      fetchResourceDetails({
        cluster_id: props.clusterId,
      });
      runGetMonitorUrls({
        bk_biz_id: currentBizId,
        cluster_type: ClusterTypes.MONGO_REPLICA_SET,
        cluster_id: props.clusterId,
      });
    },
    {
      immediate: true,
    },
  );

  const handleShowAccessEntry = () => {
    accessEntryInfoShow.value = true;
  };

  const handleCapacityChange = () => {
    capacityChangeShow.value = true;
  };
</script>

<style lang="less">
  .replica-set-breadcrumbs-box {
    display: flex;
    width: 100%;
    margin-left: 8px;
    font-size: 12px;
    align-items: center;

    .replica-set-breadcrumbs-box-status {
      display: flex;
      margin-left: 30px;
      align-items: center;
    }

    .replica-set-breadcrumbs-box-button {
      display: flex;
      margin-left: auto;
      align-items: center;

      .more-button {
        padding: 3px 6px;
      }
    }
  }
</style>

<style lang="less" scoped>
  .cluster-details {
    height: 100%;
    background: #fff;

    .content-tabs {
      :deep(.bk-tab-content) {
        padding: 0;
      }
    }

    .content-wrapper {
      height: calc(100vh - 168px);
      padding: 0 24px;
      overflow: auto;
    }
  }
</style>
