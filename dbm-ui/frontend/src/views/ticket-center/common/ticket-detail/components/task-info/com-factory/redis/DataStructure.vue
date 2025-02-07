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
      :label="t('待构造的集群')"
      :min-width="180">
      <template #default="{ data }: { data: RowData }">
        {{ ticketDetails.details.clusters[data.cluster_id].immute_domain }}
      </template>
    </BkTableColumn>
    <BkTableColumn :label="t('架构版本')">
      <template #default="{ data }: { data: RowData }">
        {{ ticketDetails.details.clusters[data.cluster_id].cluster_type_name }}
      </template>
    </BkTableColumn>
    <BkTableColumn :label="t('待构造的实例')">
      <template #default="{ data }: { data: RowData }">
        <p
          v-for="item in data.master_instances"
          :key="item">
          {{ item }}
        </p>
      </template>
    </BkTableColumn>
    <BkTableColumn :label="t('规格需求')">
      <template #default="{ data }: { data: RowData }">
        {{ ticketDetails.details.specs[data.resource_spec.redis.spec_id].name }}
      </template>
    </BkTableColumn>
    <BkTableColumn :label="t('构造主机数量')">
      <template #default="{ data }: { data: RowData }">
        {{ data.resource_spec.redis.count }}
      </template>
    </BkTableColumn>
    <BkTableColumn :label="t('构造到指定时间')">
      <template #default="{ data }: { data: RowData }">
        {{ utcDisplayTime(data.recovery_time_point) }}
      </template>
    </BkTableColumn>
  </BkTable>
</template>

<script setup lang="tsx">
  import { useI18n } from 'vue-i18n';

  import TicketModel, { type Redis } from '@services/model/ticket/ticket';

  import { TicketTypes } from '@common/const';

  import { utcDisplayTime } from '@utils';

  interface Props {
    ticketDetails: TicketModel<Redis.DataStructure>;
  }

  type RowData = Props['ticketDetails']['details']['infos'][number];

  defineProps<Props>();

  defineOptions({
    name: TicketTypes.REDIS_DATA_STRUCTURE,
    inheritAttrs: false,
  });

  const { t } = useI18n();
</script>
