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
  <span
    v-bk-tooltips="{
      content: disableTips,
      disabled: !disableTips,
    }">
    <TableEditInput
      ref="inputRef"
      v-model="localIpText"
      :disabled="Boolean(disableTips)"
      :placeholder="t('请输入单个 IP')"
      :rules="rules"
      textarea />
  </span>
</template>
<script lang="ts">
  const instanceKey = `slave_host_${random()}`;
  const singleHostSelectMemo: { [key: string]: Record<string, boolean> } = {};
</script>
<script setup lang="ts">
  import _ from 'lodash';
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import { getHostTopoInfos } from '@services/source/ipchooser';

  import { ipv4 } from '@common/regex';

  import TableEditInput from '@components/render-table/columns/input/index.vue';

  import { random } from '@utils';

  import type { IDataRow, IHostData } from './Row.vue';

  type HostTopoInfo = ServiceReturnType<typeof getHostTopoInfos>['hosts_topo_info'][number];

  interface Props {
    modelValue?: IHostData;
    clusterData?: IDataRow['clusterData'];
  }

  interface Exposes {
    getValue: () => Promise<IHostData>;
  }

  const props = defineProps<Props>();

  const genHostKey = (hostData: HostTopoInfo) => `#${hostData.bk_cloud_id}#${hostData.ip}`;

  const { t } = useI18n();

  const inputRef = ref();
  const localIpText = ref('');

  const disableTips = computed(() => (props.clusterData ? '' : t('请先选择集群')));

  let hostMemo = {} as HostTopoInfo;

  const rules = [
    {
      validator: (value: string) => ipv4.test(_.trim(value)),
      message: t('IP格式不正确'),
    },
    {
      validator: (value: string) =>
        getHostTopoInfos({
          filter_conditions: {
            bk_host_innerip: [value],
            mode: 'idle_only',
          },
          bk_biz_id: window.PROJECT_CONFIG.BIZ_ID,
        }).then((data) => {
          const [newHost] = data.hosts_topo_info;
          if (!newHost) {
            return t('ips不在空闲机中', { ips: value });
          }

          if (newHost.bk_cloud_id !== props.clusterData!.cloudId) {
            return t('新主机xx跟目标集群xx须在同一个管控区域', {
              ip: value,
              cluster: props.clusterData!.domain,
            });
          }

          hostMemo = newHost;
          // IP 有效
          singleHostSelectMemo[instanceKey] = {};
          singleHostSelectMemo[instanceKey][genHostKey(newHost)] = true;

          return true;
        }),
      message: t('IP不存在'),
    },
    {
      validator: () => {
        const otherHostSelectMemo = { ...singleHostSelectMemo };
        delete otherHostSelectMemo[instanceKey];

        const otherAllSelectHostMap = Object.values(otherHostSelectMemo).reduce(
          (result, selectItem) => ({
            ...result,
            ...selectItem,
          }),
          {} as Record<string, boolean>,
        );
        if (otherAllSelectHostMap[genHostKey(hostMemo)]) {
          return false;
        }

        return true;
      },
      message: t('IP重复'),
    },
  ];

  // 同步外部主从机器
  watch(
    () => props.modelValue,
    () => {
      localIpText.value = props.modelValue ? props.modelValue.ip : '';
    },
    {
      immediate: true,
    },
  );

  defineExpose<Exposes>({
    getValue() {
      const formatHost = (item: HostTopoInfo) => ({
        bk_biz_id: window.PROJECT_CONFIG.BIZ_ID,
        bk_host_id: item.bk_host_id,
        bk_cloud_id: item.bk_cloud_id,
        ip: item.ip,
      });
      return inputRef.value.getValue().then(() =>
        Promise.resolve({
          new_slave_host: formatHost(hostMemo),
        }),
      );
    },
  });
</script>
