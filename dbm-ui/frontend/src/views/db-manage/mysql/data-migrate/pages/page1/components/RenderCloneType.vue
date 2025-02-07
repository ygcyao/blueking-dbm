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
  <TableEditSelect
    ref="editSelectRef"
    v-model="modelValue"
    :list="list"
    :placeholder="t('请选择')"
    :rules="rules"
    @change="(value) => handleChange(value as string)" />
</template>
<script setup lang="ts">
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import TableEditSelect from '@components/render-table/columns/select/index.vue';

  interface Emits {
    (e: 'change', value: string): void;
  }

  interface Exposes {
    getValue: () => Promise<{
      data_schema_grant: string;
    }>;
  }

  const emits = defineEmits<Emits>();

  const modelValue = defineModel<string>({
    default: 'data,schema',
  });

  const { t } = useI18n();

  const editSelectRef = ref();

  const rules = [
    {
      validator: (value: string) => Boolean(value),
      message: t('不能为空'),
    },
  ];

  const list = [
    {
      value: 'data,schema',
      label: t('克隆表结构和数据'),
    },
    {
      value: 'schema',
      label: t('克隆表结构'),
    },
  ];

  const handleChange = (value: string) => {
    emits('change', value);
  };

  defineExpose<Exposes>({
    getValue() {
      return editSelectRef.value.getValue().then(() => ({
        data_schema_grant: modelValue.value,
      }));
    },
  });
</script>
