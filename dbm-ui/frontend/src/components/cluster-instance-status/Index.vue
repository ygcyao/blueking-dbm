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
  <div class="db-cluster-instance-status">
    <DbIcon
      svg
      :type="clusterInstStatus[data as keyof typeof clusterInstStatus].icon" />
    <span
      v-if="showText"
      style="margin-left: 4px">
      {{ clusterInstStatus[data as keyof typeof clusterInstStatus].text }}
    </span>
  </div>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  interface Props {
    data: string;
    showText?: boolean;
  }

  withDefaults(defineProps<Props>(), {
    showText: true,
  });

  const { t } = useI18n();

  const clusterInstStatus = {
    running: {
      text: t('正常'),
      icon: 'normal',
    },
    unavailable: {
      text: t('异常'),
      icon: 'abnormal',
    },
    restoring: {
      text: t('重建中'),
      icon: 'sync-pending',
    },
  };
</script>
<style lang="less">
  .db-cluster-status {
    display: flex;
    align-items: center;
  }
</style>
