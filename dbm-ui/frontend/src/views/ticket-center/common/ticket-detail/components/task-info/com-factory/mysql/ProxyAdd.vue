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
  <BkTable :data="ticketDetails.details.infos">
    <BkTableColumn
      :label="t('目标集群')"
      :min-width="250">
      <template #default="{ data }: { data: RowData }">
        <div
          v-for="clusterId in data.cluster_ids"
          :key="clusterId"
          style="line-height: 20px">
          {{ ticketDetails.details.clusters[clusterId].immute_domain }}
        </div>
      </template>
    </BkTableColumn>
    <BkTableColumn :label="t('新Proxy主机')">
      <template #default="{ data }: { data: RowData }">
        {{ data?.new_proxy?.ip }}
      </template>
    </BkTableColumn>
  </BkTable>
</template>
<script setup lang="ts">
  import { useI18n } from 'vue-i18n';

  import TicketModel, { type Mysql } from '@services/model/ticket/ticket';

  import { TicketTypes } from '@common/const';

  interface Props {
    ticketDetails: TicketModel<Mysql.ProxyAdd>;
  }

  type RowData = Props['ticketDetails']['details']['infos'][number];

  defineProps<Props>();

  defineOptions({
    name: TicketTypes.MYSQL_PROXY_ADD,
    inheritAttrs: false,
  });

  const { t } = useI18n();
</script>
