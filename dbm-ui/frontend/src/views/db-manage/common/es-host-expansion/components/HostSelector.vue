<template>
  <div>
    <IpSelector
      :biz-id="bizId"
      class="mt-12"
      :cloud-info="cloudInfo"
      :disable-host-method="disableHostMethod"
      :os-types="[OSTypes.Linux]"
      :show-view="false"
      @change="handleHostChange">
      <template #submitTips="{ hostList }">
        <I18nT
          keypath="已选n台_共nGB"
          style="font-size: 14px; color: #63656e"
          tag="span">
          <span
            class="number"
            style="color: #2dcb56">
            {{ hostList.length }}
          </span>
          <span
            class="number"
            style="color: #3a84ff">
            {{ calcSelectHostDisk(hostList) }}
          </span>
          <!-- <span
            class="number"
            style="color: #63656e">
            {{ data.targetDisk - data.totalDisk }}
          </span> -->
        </I18nT>
      </template>
    </IpSelector>
    <div
      v-if="hostTableData.length > 0"
      class="data-preview-table">
      <div class="data-preview-header">
        <I18nT keypath="共n台_共nGB">
          <span
            class="number"
            style="color: #3a84ff">
            {{ hostTableData.length }}
          </span>
          <span
            class="number"
            style="color: #2dcb56">
            {{ calcSelectHostDisk(hostTableData) }}
          </span>
        </I18nT>
      </div>
      <BkTable
        :columns="tableColumns"
        :data="hostTableData" />
    </div>
  </div>
</template>
<script setup lang="tsx">
  import {
    computed,
    shallowRef,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import type { HostInfo } from '@services/types';

  import { useGlobalBizs } from '@stores';

  import { OSTypes } from '@common/const';

  import HostAgentStatus from '@components/host-agent-status/Index.vue';
  import IpSelector from '@components/ip-selector/IpSelector.vue';

  import EditHostInstance from '@views/db-manage/common/big-data-host-table/es-host-table/components/EditHostInstance.vue';

  import type { TExpansionNode } from '../Index.vue';

  interface Props {
    cloudInfo: {
      id: number,
      name: string
    },
    data: TExpansionNode,
    disableHostMethod?: (params: HostInfo) => string | boolean
  }

  interface Emits {
    (e: 'change', value: TExpansionNode['hostList'], expansionDisk: TExpansionNode['expansionDisk']): void,
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const calcSelectHostDisk = (hostList: HostInfo[]) => hostList
    .reduce((result, hostItem) => result + ~~Number(hostItem.bk_disk), 0);


  const { t } = useI18n();
  const globalBizsStore = useGlobalBizs();

  const bizId = globalBizsStore.currentBizId;

  const isClientNode = computed(() => props.data.role === 'es_client');
  const hostTableData = shallowRef<TExpansionNode['hostList']>(props.data.hostList || []);

  const tableColumns = computed(() => {
    const baseColumns = [
      {
        label: t('节点 IP'),
        field: 'ip',
        render: ({ data }: {data: TExpansionNode['hostList'][number]}) => data.ip || '--',
      },
      {
        label: t('Agent状态'),
        field: 'alive',
        render: ({ data }: {data: TExpansionNode['hostList'][number]}) => <HostAgentStatus data={data.alive} />,
      },
      {
        label: t('磁盘_GB'),
        field: 'bk_disk',
        render: ({ data }: {data: TExpansionNode['hostList'][number]}) => data.bk_disk || '--',
      },
      {
        label: t('操作'),
        width: 100,
        render: ({ data }: {data: TExpansionNode['hostList'][number]}) => (
        <bk-button
          text
          theme="primary"
          onClick={() => handleRemoveHost(data)}>
          {t('删除')}
        </bk-button>
      ),
      },
    ];
    if (!isClientNode.value) {
      baseColumns.splice(1, 0, {
        label: t('每台主机实例数'),
        width: 150,
        render: ({ data }: {data: TExpansionNode['hostList'][number]}) => (
          <EditHostInstance
            modelValue={data.instance_num}
            onChange={(value: number) => handleInstanceNumChange(value, data)}  />
        ),
      });
    }
    return baseColumns;
  });

  const handleHostChange = (hostList: TExpansionNode['hostList']) => {
    hostTableData.value = hostList.map((item) => {
      if (!isClientNode.value) {
        return Object.assign({}, item, {
          instance_num: 1,
        });
      }
      return item;
    });
    emits('change', hostTableData.value, calcSelectHostDisk(hostList));
  };

  const handleInstanceNumChange = (value: number, data: TExpansionNode['hostList'][number]) => {
    const hostList = hostTableData.value.map((item) => {
      if (item.host_id === data.host_id) {
        return {
          ...item,
          instance_num: value,
        };
      }
      return item;
    });
    hostTableData.value = hostList;
    emits('change', hostList, calcSelectHostDisk(hostList));
  };

  const handleRemoveHost = (data: TExpansionNode['hostList'][0]) => {
    const hostList = hostTableData.value.reduce((result, item) => {
      if (item.host_id !== data.host_id) {
        result.push(item);
      }
      return result;
    }, [] as TExpansionNode['hostList']);
    hostTableData.value = hostList;
    emits('change', hostList, calcSelectHostDisk(hostList));
  };
</script>
