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
  <div class="cluster-shrink-node-status-box">
    <div
      v-for="nodeItem in list"
      :key="nodeItem.key"
      class="node-item"
      :class="{ active: modelValue === nodeItem.key }"
      @click="handleSelect(nodeItem.key)">
      <div class="node-item-name">
        {{ nodeItem.label }}
      </div>
      <template v-if="validateStatusMemo[nodeItem.key]">
        <div
          v-if="nodeItem.key === 'observer' && nodeInfo[nodeItem.key].nodeList.length > 0"
          class="disk-tips">
          <span class="number">{{ nodeInfo[nodeItem.key].nodeList.length }}</span>
          <span>{{ t('台') }}</span>
        </div>
        <div
          v-else-if="nodeInfo[nodeItem.key].shrinkDisk"
          class="disk-tips">
          <span class="number">{{ nodeInfo[nodeItem.key].shrinkDisk }}</span>
          <span>G</span>
        </div>
        <div
          v-else
          class="empty-tips">
          <span>{{ t('未填写') }}</span>
        </div>
      </template>
    </div>
  </div>
</template>
<script
  setup
  lang="ts"
  generic="T extends EsNodeModel | HdfsNodeModel | KafkaNodeModel | PulsarNodeModel | DorisNodeModel">
  import { useI18n } from 'vue-i18n';

  import DorisNodeModel from '@services/model/doris/doris-node';
  import EsNodeModel from '@services/model/es/es-node';
  import HdfsNodeModel from '@services/model/hdfs/hdfs-node';
  import KafkaNodeModel from '@services/model/kafka/kafka-node';
  import PulsarNodeModel from '@services/model/pulsar/pulsar-node';

  import type { TShrinkNode } from './Index.vue';

  interface Props {
    list: Array<{
      key: string;
      label: string;
    }>;
    nodeInfo: Record<string, TShrinkNode<T>>;
  }
  interface Exposes {
    validate: () => boolean;
  }

  const props = defineProps<Props>();

  const modelValue = defineModel<string>({
    required: true,
  });

  const { t } = useI18n();

  const validateStatusMemo = reactive(
    props.list.reduce(
      (result, item) => ({
        ...result,
        [item.key]: false,
      }),
      {} as Record<string, boolean>,
    ),
  );

  const handleSelect = (value: string) => {
    validateStatusMemo[modelValue.value] = true;
    modelValue.value = value;
  };

  defineExpose<Exposes>({
    validate() {
      Object.keys(validateStatusMemo).forEach((key) => (validateStatusMemo[key] = true));
      return Object.values(props.nodeInfo).some((nodeData) => nodeData.nodeList.length > 0);
    },
  });
</script>
<style lang="less">
  .cluster-shrink-node-status-box {
    width: 185px;
    padding: 12px;
    background: #fff;
    border-right: 1px solid #f0f1f5;

    .node-item {
      display: flex;
      height: 32px;
      padding: 0 8px;
      font-size: 12px;
      color: #63656e;
      cursor: pointer;
      background: #f5f7fa;
      align-items: center;
      transition: 0.1s;

      &:hover {
        background: #f0f5ff;
      }

      &.active {
        font-weight: bold;
        color: #3a84ff;
        background: #f0f5ff;
      }

      & ~ .node-item {
        margin-top: 4px;
      }

      .node-item-name {
        padding-right: 8px;
        overflow: hidden;
        text-overflow: ellipsis;
        flex: 0 1 auto;
      }
    }

    .empty-tips {
      margin-left: auto;
      font-weight: normal;
      color: #c4c6cc;
      flex: 0 0 auto;
    }

    .disk-tips {
      margin-left: auto;
      font-weight: normal;
      color: #63656e;
      flex: 0 0 auto;
    }
  }
</style>
