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
  <div class="doris-observer-host-shrink">
    <div class="header-box">
      <span class="header-label">{{ data.label }}</span>
      <BkTag
        class="ml-8"
        theme="info">
        {{ data.tagText }}
      </BkTag>
    </div>
    <BkAlert
      v-if="isDisabled"
      class="mb16"
      theme="warning">
      <template #title>
        <I18nT keypath="当前仅剩n台 IP_无法缩容">
          <span>{{ data.originalNodeList.length }}</span>
        </I18nT>
      </template>
    </BkAlert>
    <BkForm form-type="vertical">
      <BkFormItem :label="t('目标容量')">
        <div class="target-content-box">
          <div class="content-label">
            {{ t('缩容至') }}
          </div>
          <div class="content-value">
            <div>
              <BkInput
                clearable
                :disabled="isDisabled"
                :max="data.originalNodeList.length"
                :min="1"
                :model-value="localTargetDisk > 0 ? localTargetDisk : undefined"
                :placeholder="t('请输入')"
                style="width: 156px; margin-right: 8px"
                type="number"
                @change="handleTargetDiskChange" />
              <span>{{ t('台') }}</span>
              <template v-if="localTargetDisk > 0">
                <span> , {{ t('共缩容') }} </span>
                <span
                  class="strong-num"
                  style="color: #2dcb56">
                  {{ data.originalNodeList.length - localTargetDisk }}
                </span>
                <span>{{ t('台') }}</span>
              </template>
            </div>
            <div class="content-tips">
              <span>
                {{ t('当前数量') }}:
                <span class="strong-num">{{ data.originalNodeList.length }}</span>
                {{ t('台') }}
              </span>
              <span v-if="data.minHost > 0">，{{ t('至少保留n台', { n: data.minHost }) }}</span>
            </div>
          </div>
        </div>
      </BkFormItem>
      <BkFormItem>
        <template #label>
          <span>{{ t('缩容的节点 IP') }}</span>
          <span style="font-weight: normal; color: #979ba5">
            {{ t('（默认从节点列表选取，如不满足，可以手动添加）') }}
          </span>
        </template>
        <div class="data-preview-table">
          <div class="data-preview-header">
            <div v-if="!data.targetDisk">
              {{ t('请先设置期望容量') }}
            </div>
            <template v-else>
              <I18nT
                v-if="data.targetDisk"
                keypath="共n台，共nG">
                <span
                  class="number"
                  style="color: #3a84ff">
                  {{ nodeTableData.length }}
                </span>
                <span
                  class="number"
                  style="color: #2dcb56">
                  {{ data.shrinkDisk }}
                </span>
              </I18nT>
              <div
                v-if="targetMatchReal"
                class="ml-8">
                <I18nT
                  v-if="targetMatchReal > 0"
                  class="ml-8"
                  keypath="较目标容量相差n台">
                  <span
                    class="number"
                    style="color: #ff9c01">
                    {{ targetMatchReal }}
                  </span>
                </I18nT>
                <I18nT
                  v-if="targetMatchReal < 0"
                  class="ml-8"
                  keypath="较目标容量超出n台">
                  <span
                    class="number"
                    style="color: #ff9c01">
                    {{ Math.abs(targetMatchReal) }}
                  </span>
                </I18nT>
              </div>
              <BkButton
                v-if="data.targetDisk"
                size="small"
                style="margin-left: auto"
                @click="handleShowHostSelect">
                <DbIcon type="add" />
                {{ t('手动添加') }}
              </BkButton>
            </template>
          </div>
          <BkTable
            v-if="nodeTableData.length > 0"
            :columns="tableColumns"
            :data="nodeTableData" />
        </div>
      </BkFormItem>
    </BkForm>
    <SelectOriginalHost
      v-model:is-show="isShowHostDialog"
      :min-host="data.minHost"
      :model-value="data.nodeList"
      :original-node-list="data.originalNodeList"
      :target-disk="data.totalDisk - localTargetDisk"
      @change="handleSelectChange" />
  </div>
</template>
<script setup lang="tsx">
  import { useI18n } from 'vue-i18n';

  import DorisNodeModel from '@services/model/doris/doris-node'

  import RenderHostStatus from '@components/render-host-status/Index.vue';

  import SelectOriginalHost from '@views/db-manage/common/host-shrink/components/SelectOriginalHost.vue';

  export interface TShrinkNode<N> {
    // 节点显示名称
    label: string,
    // 原始节点列表
    originalNodeList: N[],
    // 缩容后的节点列表
    nodeList: N[],
    // 原始磁盘大小
    totalDisk: number,
    // 缩容目标磁盘大小
    targetDisk: number,
    // 选择节点后实际的缩容磁盘大小
    shrinkDisk: number,
    // 改节点所需的最少主机数
    minHost: number,
    // 节点类型 tag 文本
    tagText: string;
  }

  interface Props {
    data: TShrinkNode<DorisNodeModel>,
  }

  interface Emits {
    (e: 'change', value: Props['data']['nodeList']): void,
    (e: 'target-disk-change', value: Props['data']['totalDisk']): void,
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const localTargetDisk = ref(props.data.targetDisk);
  const nodeTableData = shallowRef<Props['data']['nodeList']>(props.data.nodeList || []);
  const isShowHostDialog = ref(false);

  const isDisabled = computed(() => props.data.originalNodeList.length <= props.data.minHost);

  // 台数误差
  const targetMatchReal = computed(() => props.data.originalNodeList.length - localTargetDisk.value - nodeTableData.value.length);

  const tableColumns = [
    {
      label: t('节点 IP'),
      field: 'ip',
      render: ({ data }: { data: Props['data']['nodeList'][0] }) => data.ip || '--',
    },
    {
      label: t('Agent状态'),
      field: 'alive',
      render: ({ data }: { data: Props['data']['nodeList'][0] }) => <RenderHostStatus data={data.status} />
    },
    {
      label: t('磁盘_GB'),
      field: 'disk',
      render: ({ data }: { data: Props['data']['nodeList'][0] }) => data.disk || '--',
    },
    {
      label: t('操作'),
      width: 100,
      render: ({ data }: { data: Props['data']['nodeList'][0] }) => (
        <bk-button
          text
          theme="primary"
          onClick={() => handleRemoveHost(data)}>
          {t('删除')}
        </bk-button>
      ),
    },
  ];

  // 调整目标容量时需要自动匹配
  watch(localTargetDisk, () => {
    const nodeList = props.data.originalNodeList.slice(0, props.data.originalNodeList.length - localTargetDisk.value)
    nodeTableData.value = nodeList

    emits('change', nodeList);
  });

  // 更新目标容量
  const handleTargetDiskChange = (value: Props['data']['totalDisk']) => {
    localTargetDisk.value = value;
    window.changeConfirm = true;
    emits('target-disk-change', value);
  };

  const handleShowHostSelect = () => {
    isShowHostDialog.value = true;
  };

  // 添加节点
  const handleSelectChange = (nodeList: Props['data']['nodeList']) => {
    nodeTableData.value = nodeList;
    window.changeConfirm = true;
    emits('change', nodeList);
  };

  // 删除选择的节点
  const handleRemoveHost = (data: Props['data']['nodeList'][0]) => {
    const nodeList = nodeTableData.value.reduce((result, item) => {
      if (item.bk_host_id !== data.bk_host_id) {
        result.push(item);
      }
      return result;
    }, [] as Props['data']['nodeList']);

    nodeTableData.value = nodeList;
    window.changeConfirm = true;
    emits('change', nodeList);
  };
</script>
<style lang="less">
  .doris-observer-host-shrink {
    padding: 0 24px 24px;

    .bk-form-label {
      font-size: 12px;
      font-weight: bold;
      color: #63656e;
    }

    .header-box {
      padding: 10px 0;
      font-size: 14px;
      color: #313238;

      .header-box-label {
        font-weight: bold;
      }
    }

    .target-content-box {
      display: flex;
      align-items: flex-start;

      .content-label {
        padding-right: 8px;
      }

      .content-value {
        flex: 1;
      }

      .content-tips {
        display: flex;
        height: 40px;
        padding: 0 16px;
        margin-top: 12px;
        background: #fafbfd;
        align-items: center;
      }
    }

    .strong-num {
      padding: 0 4px;
      font-weight: bold;
    }

    .data-preview-table {
      margin-top: 16px;

      .data-preview-header {
        display: flex;
        height: 42px;
        padding: 0 16px;
        background: #f0f1f5;
        align-items: center;
      }
    }
  }
</style>
