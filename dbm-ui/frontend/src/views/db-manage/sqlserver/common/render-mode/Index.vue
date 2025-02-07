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
  <div class="render-mode">
    <div style="width: 140px">
      <TableEditSelect
        v-model="localBackupType"
        :disabled="editDisabled"
        :list="targetList"
        @change="hanldeBackupTypeChange" />
    </div>
    <div style="flex: 1">
      <TableEditDateTime
        v-if="localBackupType === 'time'"
        ref="localRollbackTimeRef"
        v-model="resotreTime"
        :disabled="editDisabled"
        :disabled-date="disableDate"
        :rules="timerRules"
        type="datetime" />

      <div
        v-else
        class="local-backup-select">
        <RecordSelector
          ref="localBackupFileRef"
          v-model="restoreBackupFile"
          :cluster-id="clusterId"
          :disabled="editDisabled" />
      </div>
    </div>
  </div>
</template>
<script setup lang="tsx">
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import { queryBackupLogs } from '@services/source/sqlserver';

  import { useTimeZoneFormat } from '@hooks';

  import TableEditDateTime from '@components/render-table/columns//DateTime.vue';
  import TableEditSelect from '@components/render-table/columns/select/index.vue';

  import RecordSelector from './RecordSelector.vue';

  interface Props {
    clusterId?: number;
  }

  interface Exposes {
    getValue: () => Promise<{
      restore_backup_file?: any;
      restore_time?: string;
    }>;
  }

  const props = defineProps<Props>();

  const disableDate = (date: Date) => date && date.valueOf() > Date.now();

  const { t } = useI18n();
  const { format: formatDateToUTC } = useTimeZoneFormat();

  const timerRules = [
    {
      validator: (value: string) => !!value,
      message: t('回档时间不能为空'),
    },
  ];
  const targetList = [
    {
      value: 'record',
      label: t('备份记录'),
    },
    {
      value: 'time',
      label: t('回档到指定时间'),
    },
  ];

  const restoreBackupFile = defineModel<ServiceReturnType<typeof queryBackupLogs>[number]>('restoreBackupFile');
  const resotreTime = defineModel<string>('restoreTime', {
    default: '',
  });

  const localRollbackTimeRef = ref<InstanceType<typeof TableEditDateTime>>();
  const localBackupFileRef = ref<InstanceType<typeof RecordSelector>>();
  const localBackupType = ref('record');

  const editDisabled = computed(() => !props.clusterId);

  const hanldeBackupTypeChange = () => {
    resotreTime.value = '';
  };

  watch(
    () => props.clusterId,
    () => {},
  );
  watch(
    () => props.clusterId,
    () => {
      restoreBackupFile.value = undefined;
      resotreTime.value = '';
    },
    {
      immediate: true,
    },
  );

  watch(
    [resotreTime, restoreBackupFile],
    () => {
      localBackupType.value = resotreTime.value ? 'time' : 'record';
    },
    {
      immediate: true,
    },
  );

  defineExpose<Exposes>({
    getValue() {
      if (localBackupType.value === 'record') {
        return localBackupFileRef.value!.getValue().then((data) => ({
          restore_backup_file: data,
        }));
      }
      return localRollbackTimeRef.value!.getValue().then(() => ({
        restore_time: formatDateToUTC(resotreTime.value),
      }));
    },
  });
</script>
<style lang="less" scoped>
  .render-mode {
    display: flex;

    .action-item {
      overflow: hidden;

      &:first-child {
        flex: 1;
      }

      &:last-child {
        flex: 2;
      }
    }
  }

  .local-backup-select {
    position: relative;

    :deep(.table-edit-select),
    :deep(.rollback-mode-select) {
      .select-result-text {
        padding-left: 14px;
      }

      .select-placeholder {
        left: 30px;
      }
    }

    .file-flag {
      position: absolute;
      top: 14px;
      left: 8px;
      z-index: 1;
      font-size: 16px;
      color: #c4c6cc;
    }
  }
</style>
