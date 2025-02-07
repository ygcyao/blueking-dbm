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
  <div
    v-bkloading="{ loading: isLoading }"
    class="config-info">
    <ScrollFaker>
      <DbOriginalTable
        :columns="columns"
        :data="data.conf_items" />
    </ScrollFaker>
  </div>
</template>

<script setup lang="tsx">
  import { useI18n } from 'vue-i18n';

  import { getLevelConfig } from '@services/source/configs';

  import { useGlobalBizs } from '@stores';

  import { ClusterTypes } from '@common/const';

  interface Props {
    queryInfos: {
      version: string;
      clusterId: number;
    };
  }

  type IRowData = ServiceReturnType<typeof getLevelConfig>['conf_items'][number];

  const props = defineProps<Props>();

  const { currentBizId } = useGlobalBizs();
  const { t } = useI18n();

  const isLoading = ref(false);
  const data = shallowRef({
    name: '',
    version: '',
    description: '',
    conf_items: [],
  } as ServiceReturnType<typeof getLevelConfig>);
  const columns = [
    {
      label: t('参数项'),
      field: 'conf_name',
      render: ({ data }: { data: IRowData }) => data.conf_name,
    },
    {
      label: t('参数值'),
      field: 'conf_value',
      render: ({ data }: { data: IRowData }) => data.conf_value,
    },
    {
      label: t('描述'),
      field: 'description',
      render: ({ data }: { data: IRowData }) => data.description || '--',
    },
  ];

  watch(
    () => props.queryInfos,
    (infos) => {
      const { version, clusterId } = infos;
      if (version && clusterId) {
        isLoading.value = true;
        getLevelConfig({
          bk_biz_id: currentBizId,
          level_value: props.queryInfos.clusterId,
          meta_cluster_type: ClusterTypes.REDIS,
          level_name: 'cluster',
          conf_type: 'dbconf',
          version: props.queryInfos.version,
        })
          .then((res) => {
            data.value = res;
          })
          .finally(() => {
            isLoading.value = false;
          });
      }
    },
    {
      immediate: true,
      deep: true,
    },
  );
</script>

<style lang="less" scoped>
  .config-info {
    height: calc(100% - 96px);
    margin: 24px 0;
  }
</style>
