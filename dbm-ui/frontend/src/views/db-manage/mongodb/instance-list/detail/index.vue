<template>
  <div
    v-bkloading="{ loading: isLoading }"
    class="instance-details">
    <BkTab
      v-model:active="activePanel"
      class="content-tabs"
      type="card-tab">
      <BkTabPanel
        :label="t('基本信息')"
        name="info" />
      <BkTabPanel
        :label="t('参数配置')"
        name="config" />
    </BkTab>
    <div class="content-wrapper">
      <BaseInfo
        v-if="activePanel === 'info' && data"
        :data="data" />
      <Config
        v-if="activePanel === 'config' && data"
        :data="data" />
    </div>
  </div>
</template>

<script setup lang="tsx">
  import { useI18n } from 'vue-i18n';
  import { useRequest } from 'vue-request';

  import { retrieveMongoInstanceDetail } from '@services/source/mongodb';

  import BaseInfo from './components/BaseInfo.vue';
  import Config from './components/Config.vue';

  interface Props {
    instanceData: {
      instanceAddress: string;
      clusterId: number;
    };
  }

  const props = defineProps<Props>();

  const { t } = useI18n();

  const activePanel = ref('info');

  const {
    loading: isLoading,
    run: fetchInstDetails,
    data,
  } = useRequest(retrieveMongoInstanceDetail, {
    manual: true,
  });

  watch(
    () => props.instanceData,
    () => {
      fetchInstDetails({
        instance_address: props.instanceData.instanceAddress,
        cluster_id: props.instanceData.clusterId,
      });
    },
    {
      immediate: true,
    },
  );
</script>

<style lang="less" scoped>
  .instance-details {
    height: 100%;
    background: #fff;

    .content-tabs {
      :deep(.bk-tab-content) {
        padding: 0;
      }
    }

    .content-wrapper {
      height: 100%;
      padding: 0 24px;
      overflow: auto;
    }
  }
</style>
