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
  <BkLoading
    class="es-cluster-expansion-box"
    :loading="isLoading">
    <BkAlert
      class="mb16"
      theme="warning"
      :title="$t('冷热节点至少扩容一种类型')" />
    <BkRadioGroup
      v-model="ipSource"
      class="ip-srouce-box">
      <BkRadioButton label="resource_pool">
        {{ $t('资源池自动匹配') }}
      </BkRadioButton>
      <BkRadioButton label="manual_input">
        {{ $t('手动选择') }}
      </BkRadioButton>
    </BkRadioGroup>
    <div class="wrapper">
      <NodeStatusList
        ref="nodeStatusListRef"
        v-model="nodeType"
        :ip-source="ipSource"
        :list="nodeStatusList"
        :node-info="nodeInfoMap" />
      <div class="node-panel">
        <HostExpansion
          v-if="!isLoading"
          :key="nodeType"
          v-model:expansion-disk="nodeInfoMap[nodeType].expansionDisk"
          v-model:host-list="nodeInfoMap[nodeType].hostList"
          v-model:resource-spec="nodeInfoMap[nodeType].resourceSpec"
          :cloud-info="{
            id: data.bk_cloud_id,
            name: data.bk_cloud_name,
          }"
          :data="nodeInfoMap[nodeType]"
          :disable-host-method="disableHostMethod"
          :ip-source="ipSource" />
      </div>
    </div>
  </BkLoading>
</template>
<script setup lang="tsx">
  import { InfoBox } from 'bkui-vue';
  import {
    reactive,
    ref,
  } from 'vue';
  import { useI18n } from 'vue-i18n';

  import ESModel from '@services/model/es/es';
  import EsMachineModel from '@services/model/es/es-machine';
  import { getEsMachineList } from '@services/source/es'
  import { createTicket } from '@services/source/ticket';
  import type { HostInfo } from '@services/types'

  import { useTicketMessage } from '@hooks';

  import { useGlobalBizs } from '@stores';

  import { ClusterTypes } from '@common/const';

  import HostExpansion, {
    type TExpansionNode,
  } from '@views/db-manage/common/es-host-expansion/Index.vue';
  import NodeStatusList from '@views/db-manage/common/host-expansion/NodeStatusList.vue';

  import { messageError } from '@utils';

  interface Props {
    data: ESModel,
  }

  interface Emits {
    (e: 'change'): void
  }

  interface Exposes {
    submit: () => Promise<any>
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const makeMapByHostId = (hostList: TExpansionNode['hostList'] = []) => hostList.reduce((result, item) => ({
    ...result,
    [item.host_id]: true,
  }), {} as Record<number, boolean>);

  const { t } = useI18n();
  const globalBizsStore = useGlobalBizs();
  const ticketMessage = useTicketMessage();

  const bizId = globalBizsStore.currentBizId;

  const nodeStatusList = [
    {
      key: 'cold',
      label: '冷节点',
    },
    {
      key: 'hot',
      label: '热节点',
    },
    {
      key: 'client',
      label: 'Client 节点',
    },
  ];

  const nodeInfoMap = reactive<Record<string, TExpansionNode>>({
    hot: {
      label: '热节点',
      clusterId: props.data.id,
      role: 'es_datanode_hot',
      originalHostList: [],
      ipSource: 'resource_pool',
      hostList: [],
      totalDisk: 0,
      expansionDisk: 0,
      specClusterType: ClusterTypes.ES,
      specMachineType: 'es_datanode',
      resourceSpec: {
        spec_id: 0,
        count: 0,
        instance_num: 1,
      },
      tagText: t('存储层')
    },
    cold: {
      label: '冷节点',
      clusterId: props.data.id,
      role: 'es_datanode_cold',
      originalHostList: [],
      ipSource: 'resource_pool',
      hostList: [],
      totalDisk: 0,
      expansionDisk: 0,
      specClusterType: ClusterTypes.ES,
      specMachineType: 'es_datanode',
      resourceSpec: {
        spec_id: 0,
        count: 0,
        instance_num: 1,
      },
      tagText: t('存储层')
    },
    client: {
      label: 'Client 节点',
      clusterId: props.data.id,
      role: 'es_client',
      originalHostList: [],
      ipSource: 'resource_pool',
      hostList: [],
      totalDisk: 0,
      expansionDisk: 0,
      specClusterType: ClusterTypes.ES,
      specMachineType: 'es_client',
      resourceSpec: {
        spec_id: 0,
        count: 0,
        instance_num: 1,
      },
      tagText: t('接入层')
    },
  });

  const nodeStatusListRef = ref();
  const isLoading = ref(false);
  const ipSource = ref('resource_pool');
  const nodeType = ref('cold');

  // 获取主机详情
  const fetchHostDetail = () => {
    isLoading.value = true;
    getEsMachineList({
      cluster_ids: String(props.data.id),
      offset: 0,
      limit: -1
    }).then((data) => {
      const hotOriginalHostList: EsMachineModel[] = [];
      const coldOriginalHostList: EsMachineModel[] = [];

      let hotDiskTotal = 0;
      let coldDiskTotal = 0;

      data.results.forEach((hostItem) => {
        if (hostItem.isHot) {
          hotDiskTotal += Math.floor(Number(hostItem.host_info.bk_disk));
          hotOriginalHostList.push(hostItem);
        }
        if (hostItem.isCold) {
          coldDiskTotal += Math.floor(Number(hostItem.host_info.bk_disk));
          coldOriginalHostList.push(hostItem);
        }
      });

      nodeInfoMap.hot.totalDisk = hotDiskTotal;
      nodeInfoMap.hot.originalHostList = hotOriginalHostList;

      nodeInfoMap.cold.totalDisk = coldDiskTotal;
      nodeInfoMap.cold.originalHostList = coldOriginalHostList;
    })
      .finally(() => {
        isLoading.value = false;
      });
  };

  fetchHostDetail();

  // 扩容主机节点互斥
  const disableHostMethod = (hostData: HostInfo) => {
    const hotDisableHostMethod = (hostData: HostInfo) => {
      const coldHostIdMap = makeMapByHostId(nodeInfoMap.cold.hostList);
      if (coldHostIdMap[hostData.host_id]) {
        return t('主机已被xx节点使用', ['冷']);
      }
      return false;
    };
    const coldDisableHostMethod = (hostData: HostInfo) => {
      const hotHostIdMap = makeMapByHostId(nodeInfoMap.hot.hostList);
      if (hotHostIdMap[hostData.host_id]) {
        return t('主机已被xx节点使用', ['热']);
      }
      return false;
    };

    if (nodeType.value === 'hot') {
      return hotDisableHostMethod(hostData);
    }
    if (nodeType.value === 'cold') {
      return coldDisableHostMethod(hostData);
    }

    return false;
  };

  defineExpose<Exposes>({
    submit() {
      if (!nodeStatusListRef.value.validate()) {
        messageError(t('冷热节点至少扩容一种类型'));
        return Promise.reject();
      }

      const renderSubTitle = () => {
        const renderExpansionDiskTips = () => Object.values(nodeInfoMap).map((nodeData) => {
          if (nodeData.expansionDisk) {
            return (
              <div>
                {t('name容量从nG扩容至nG', {
                  name: nodeData.label,
                  totalDisk: nodeData.totalDisk,
                  expansionDisk: nodeData.totalDisk + nodeData.expansionDisk,
                })}
              </div>
            );
          }
          return null;
        });

        return (
          <div style="font-size: 14px; line-height: 28px; color: #63656E;">
            {renderExpansionDiskTips()}
          </div>
        );
      };

      return new Promise((resolve, reject) => {
        InfoBox({
          title: t('确认扩容【name】集群', { name: props.data.cluster_name }),
          subTitle: renderSubTitle,
          confirmText: t('确认'),
          cancelText: t('取消'),
          headerAlign: 'center',
          contentAlign: 'center',
          footerAlign: 'center',
          onCancel: () => reject(),
          onConfirm: () => {
            const hostData = {};

            const generateExtInfo = () => Object.entries(nodeInfoMap).reduce((results, [key, item]) => {
              const obj = {
                host_list: item.hostList,
                total_hosts: item.originalHostList.length,
                total_disk: item.totalDisk,
                // target_disk: item.targetDisk,
                expansion_disk: item.expansionDisk,
              };
              Object.assign(results, {
                [key]: obj,
              });
              return results;
            }, {} as Record<string, any>);

            if (ipSource.value === 'manual_input') {
              const fomatHost = (hostList: TExpansionNode['hostList'] = []) => hostList.map(hostItem => ({
                ip: hostItem.ip,
                bk_cloud_id: hostItem.cloud_id,
                bk_host_id: hostItem.host_id,
                bk_biz_id: hostItem.meta.bk_biz_id,
                instance_num: hostItem.instance_num,
              }));
              Object.assign(hostData, {
                nodes: {
                  hot: fomatHost(nodeInfoMap.hot.hostList),
                  cold: fomatHost(nodeInfoMap.cold.hostList),
                  // client 节点没有 instance_num
                  client: nodeInfoMap.client.hostList.map(hostItem => ({
                    ip: hostItem.ip,
                    bk_cloud_id: hostItem.cloud_id,
                    bk_host_id: hostItem.host_id,
                    bk_biz_id: hostItem.meta.bk_biz_id,
                  })),
                },
              });
            } else {
              const resourceSpec = {};
              if (nodeInfoMap.hot.resourceSpec.spec_id > 0
                && nodeInfoMap.hot.resourceSpec.count > 0) {
                Object.assign(resourceSpec, {
                  hot: nodeInfoMap.hot.resourceSpec,
                });
              }
              if (nodeInfoMap.cold.resourceSpec.spec_id > 0
                && nodeInfoMap.cold.resourceSpec.count > 0) {
                Object.assign(resourceSpec, {
                  cold: nodeInfoMap.cold.resourceSpec,
                });
              }
              if (nodeInfoMap.client.resourceSpec.spec_id > 0
                && nodeInfoMap.client.resourceSpec.count > 0) {
                // client 节点没有 instance_num
                const clientResourceSpec = { ...nodeInfoMap.client.resourceSpec } as {instance_num?: number};
                delete clientResourceSpec.instance_num;
                Object.assign(resourceSpec, {
                  client: clientResourceSpec,
                });
              }
              Object.assign(hostData, {
                resource_spec: resourceSpec,
              });
            }

            createTicket({
              bk_biz_id: bizId,
              ticket_type: 'ES_SCALE_UP',
              details: {
                ip_source: ipSource.value,
                cluster_id: props.data.id,
                ...hostData,
                ext_info: generateExtInfo(),
              },
            }).then((data) => {
              ticketMessage(data.id);
              resolve('success');
              emits('change');
            })
          },
        });
      });
    },
  });
</script>
<style lang="less">
  .es-cluster-expansion-box {
    padding: 18px 43px 18px 37px;
    font-size: 12px;
    line-height: 20px;
    color: #63656e;
    background: #f5f7fa;

    .ip-srouce-box {
      display: flex;
      margin-bottom: 16px;

      .bk-radio-button {
        flex: 1;
        background: #fff;
      }
    }

    .wrapper {
      display: flex;
      background: #fff;
      border-radius: 2px;
      box-shadow: 0 2px 4px 0 #1919290d;

      .node-panel {
        flex: 1;
      }
    }
  }
</style>
