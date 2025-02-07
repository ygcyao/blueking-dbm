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
  <div class="render-cluster-box">
    <TableEditInput
      ref="editRef"
      :model-value="localDomain"
      :placeholder="t('请输入集群')"
      :rules="rules" />
    <DbIcon
      class="cluster-btn"
      type="host-select"
      @click="handleShowClusterSelector" />
  </div>
  <ClusterSelector
    v-model:is-show="isShowBatchSelector"
    :cluster-types="[ClusterTypes.SQLSERVER_HA, ClusterTypes.SQLSERVER_SINGLE]"
    :selected="selectedClusters"
    :tab-list-config="clusterSelectorTabConfig"
    @change="handelClusterChange" />
</template>
<script lang="ts">
  const clusterIdMemo: Record<string, number> = {};
</script>
<script setup lang="ts">
  import { onBeforeUnmount, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import SqlServerHaModel from '@services/model/sqlserver/sqlserver-ha';
  import SqlServerSingleModel from '@services/model/sqlserver/sqlserver-single';
  import { filterClusters } from '@services/source/dbbase';

  import { ClusterTypes } from '@common/const';

  import ClusterSelector from '@components/cluster-selector/Index.vue';
  import TableEditInput from '@components/render-table/columns/input/index.vue';

  import { random } from '@utils';

  interface Exposes {
    getValue: (field: string) => Promise<Record<string, number>>;
  }

  const modelValue = defineModel<{
    id: number;
    domain: string;
    cloudId: number;
    majorVersion: string;
  }>();

  const { t } = useI18n();

  const instanceKey = `render_src_cluster_${random()}`;
  clusterIdMemo[instanceKey] = 0;

  const editRef = ref<InstanceType<typeof TableEditInput>>();

  const isShowBatchSelector = ref(false);
  const localDomain = ref('');

  const selectedClusters = shallowRef<{ [key: string]: (SqlServerSingleModel | SqlServerHaModel)[] }>({
    [ClusterTypes.SQLSERVER_HA]: [],
    [ClusterTypes.SQLSERVER_SINGLE]: [],
  });

  const clusterSelectorTabConfig = {
    [ClusterTypes.SQLSERVER_HA]: {
      id: ClusterTypes.SQLSERVER_HA,
      name: t('SqlServer 主从'),
      disabledRowConfig: [
        {
          handler: (data: any) => data.isOffline,
          tip: t('集群已禁用'),
        },
      ],
      multiple: false,
    },
    [ClusterTypes.SQLSERVER_SINGLE]: {
      id: ClusterTypes.SQLSERVER_SINGLE,
      name: t('SqlServer 单节点'),
      disabledRowConfig: [
        {
          handler: (data: any) => data.isOffline,
          tip: t('集群已禁用'),
        },
      ],
      multiple: false,
    },
  };

  const rules = [
    {
      validator: (value: string) => Boolean(value),
      message: t('源集群不能为空'),
    },
    {
      validator: (value: string) =>
        filterClusters<SqlServerHaModel>({
          bk_biz_id: window.PROJECT_CONFIG.BIZ_ID,
          exact_domain: value,
        }).then((data) => {
          if (data.length > 0) {
            modelValue.value = {
              id: data[0].id,
              cloudId: data[0].bk_cloud_id,
              domain: data[0].master_domain,
              majorVersion: data[0].major_version,
            };
            clusterIdMemo[instanceKey] = data[0].id;
            return true;
          }
          clusterIdMemo[instanceKey] = 0;
          modelValue.value = undefined;
          return false;
        }),
      message: t('源集群不存在'),
    },
    {
      validator: () => {
        const otherClusterIdMemo = { ...clusterIdMemo };
        delete otherClusterIdMemo[instanceKey];
        if (Object.values(otherClusterIdMemo).includes(modelValue.value!.id)) {
          return false;
        }
        return true;
      },
      message: t('源集群重复'),
    },
  ];

  // 同步外部值
  watch(
    modelValue,
    () => {
      if (modelValue.value) {
        localDomain.value = modelValue.value.domain;
        clusterIdMemo[instanceKey] = modelValue.value.id;
      } else {
        localDomain.value = '';
      }
    },
    {
      immediate: true,
    },
  );

  const handleShowClusterSelector = () => {
    isShowBatchSelector.value = true;
  };

  const handelClusterChange = (selected: { [key: string]: Array<SqlServerSingleModel | SqlServerHaModel> }) => {
    const [clusterData] = Object.values(selected)[0];
    modelValue.value = {
      id: clusterData.id,
      cloudId: clusterData.bk_cloud_id,
      domain: clusterData.master_domain,
      majorVersion: clusterData.major_version,
    };
    localDomain.value = clusterData.master_domain;
    clusterIdMemo[instanceKey] = clusterData.id;
    setTimeout(() => {
      editRef.value!.getValue();
    });
  };

  onBeforeUnmount(() => {
    delete clusterIdMemo[instanceKey];
  });

  defineExpose<Exposes>({
    getValue(field) {
      // 用户输入未完成验证
      return editRef.value!.getValue().then(() => ({
        [field]: modelValue.value!.id,
      }));
    },
  });
</script>
<style lang="less" scoped>
  .render-cluster-box {
    position: relative;

    &:hover {
      padding-right: 30px;

      .cluster-btn {
        display: flex;
      }
    }

    .cluster-btn {
      position: absolute;
      top: 0;
      right: 0;
      bottom: 0;
      display: none;
      padding: 0 10px;
      cursor: pointer;
      justify-content: center;
      align-items: center;
    }
  }
</style>
