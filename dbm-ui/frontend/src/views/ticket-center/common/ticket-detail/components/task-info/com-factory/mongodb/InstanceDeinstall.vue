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
  <BkTable
    :data="ticketDetails.details.infos"
    show-overflow-tooltip>
    <BkTableColumn
      field="domain"
      :label="t('集群')" />
    <BkTableColumn
      field="role"
      :label="t('角色')" />
    <BkTableColumn :label="t('实例')">
      <template #default="{ data }: { data: RowData }">
        {{ `${data.ip}:${data.port}` }}
      </template>
    </BkTableColumn>
  </BkTable>
</template>
<script setup lang="ts">
  import BkTable from 'bkui-vue/lib/table';
  import { useI18n } from 'vue-i18n';

  import TicketModel, { type Mongodb } from '@services/model/ticket/ticket';

  import { TicketTypes } from '@common/const';

  interface Props {
    ticketDetails: TicketModel<Mongodb.InstanceDeinstall>;
  }

  type RowData = Props['ticketDetails']['details']['infos'][number];

  defineProps<Props>();

  defineOptions({
    name: TicketTypes.MONGODB_INSTANCE_DEINSTALL,
    inheritAttrs: false,
  });

  const { t } = useI18n();
</script>
