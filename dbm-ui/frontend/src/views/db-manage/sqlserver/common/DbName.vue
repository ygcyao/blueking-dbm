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
  <TableTagInput
    ref="tagRef"
    :disabled="(checkExist || checkNotExist) && !clusterId"
    :model-value="localValue"
    :placeholder="t('请输入DB 名称，支持通配符“%”，含通配符的仅支持单个')"
    :rules="rules"
    :single="single"
    @change="handleChange">
    <template #tip>
      <div>{{ t('不允许输入系统库，如"master", "msdb", "model", "tempdb", "Monitor"') }}</div>
      <div>{{ t('DB名、表名不允许为空，忽略DB名、忽略表名不允许为 *') }}</div>
      <div>{{ t('支持 %（指代任意长度字符串）,*（指代全部）2个通配符') }}</div>
      <div>{{ t('单元格可同时输入多个对象，使用换行，空格或；，｜分隔，按 Enter 或失焦完成内容输入') }}</div>
      <div>{{ t('包含通配符时, 每一单元格只允许输入单个对象。% 不能独立使用， * 只能单独使用') }}</div>
    </template>
  </TableTagInput>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import { checkClusterDatabase } from '@services/source/dbbase';

  import TableTagInput from '@components/render-table/columns/tag-input/index.vue';

  interface Props {
    modelValue?: string[];
    clusterId?: number;
    required?: boolean;
    single?: boolean;
    checkExist?: boolean;
    checkNotExist?: boolean;
    allowAsterisk?: boolean;
  }

  interface Emits {
    (e: 'change', value: string[]): void;
    (e: 'update:modelValue', value: string[]): void;
  }

  interface Exposes {
    getValue: (field: string) => Promise<Record<string, string[]>>;
  }

  const props = withDefaults(defineProps<Props>(), {
    modelValue: undefined,
    clusterId: undefined,
    required: true,
    single: false,
    // db 已存在报错
    checkExist: false,
    // db 不存在报错
    checkNotExist: false,
    allowAsterisk: true,
  });

  const emits = defineEmits<Emits>();

  const { t } = useI18n();

  const tagRef = ref();
  const localValue = ref(props.modelValue);

  const systemDbNames = ['master', 'msdb', 'model', 'tempdb', 'Monitor'];

  const rules = [
    {
      validator: (value: string[]) => {
        if (!props.required) {
          return true;
        }
        return value && value.length > 0;
      },
      message: t('DB 名不能为空'),
    },
    {
      validator: (value: string[]) => _.every(value, (item) => !systemDbNames.includes(item)),
      message: t('不允许输入系统库和特殊库 n', { n: systemDbNames.join(',') }),
    },
    {
      validator: (value: string[]) => !_.some(value, (item) => /\*/.test(item) && item.length > 1),
      message: t('* 只能独立使用'),
      trigger: 'change',
    },
    {
      validator: (value: string[]) => {
        if (props.allowAsterisk) {
          return true;
        }

        return _.every(value, (item) => item !== '*');
      },
      message: t('不允许为 *'),
    },
    {
      validator: (value: string[]) => _.every(value, (item) => !/^%$/.test(item)),
      message: t('% 不允许单独使用'),
      trigger: 'change',
    },
    {
      validator: (value: string[]) => {
        if (_.some(value, (item) => /[*%?]/.test(item))) {
          return value.length < 2;
        }
        return true;
      },
      message: t('含通配符的单元格仅支持输入单个对象'),
      trigger: 'change',
    },
    {
      validator: (value: string[]) => {
        if (!props.checkExist) {
          return true;
        }
        if (!props.clusterId) {
          return false;
        }
        // % 通配符不需要校验存在
        if (/%$/.test(value[0]) || value[0] === '*') {
          return true;
        }
        const clearDbList = _.filter(value, (item) => !/[*%]/.test(item));
        if (clearDbList.length < 1) {
          return true;
        }
        return checkClusterDatabase({
          bk_biz_id: window.PROJECT_CONFIG.BIZ_ID,
          cluster_id: props.clusterId,
          db_list: value,
        }).then((data) => {
          const existDbList = Object.keys(data).reduce<string[]>((result, dbName) => {
            if (data[dbName]) {
              result.push(dbName);
            }
            return result;
          }, []);
          if (existDbList.length > 0) {
            return t('n 已存在', { n: existDbList.join('、') });
          }

          return true;
        });
      },
      message: t('DB 已存在'),
    },
    {
      validator: (value: string[]) => {
        if (!props.checkNotExist) {
          return true;
        }
        if (!props.clusterId) {
          return false;
        }
        const clearDbList = _.filter(value, (item) => !/[*%]/.test(item));
        if (clearDbList.length < 1) {
          return true;
        }
        return checkClusterDatabase({
          bk_biz_id: window.PROJECT_CONFIG.BIZ_ID,
          cluster_id: props.clusterId,
          db_list: value,
        }).then((data) => {
          const notExistDbList = Object.keys(data).reduce<string[]>((result, dbName) => {
            if (!data[dbName]) {
              result.push(dbName);
            }
            return result;
          }, []);
          if (notExistDbList.length > 0) {
            return t('n 不存在', { n: notExistDbList.join('、') });
          }

          return true;
        });
      },
      message: t('DB 不存在'),
    },
  ];

  // 集群改变时 DB 需要重置
  watch(
    () => props.clusterId,
    () => {
      localValue.value = [];
    },
  );

  watch(
    () => props.modelValue,
    () => {
      if (props.modelValue) {
        localValue.value = props.modelValue;
      } else {
        localValue.value = [];
      }
    },
    {
      immediate: true,
    },
  );

  const handleChange = (value: string[]) => {
    localValue.value = value;
    emits('update:modelValue', value);
    emits('change', value);
  };

  defineExpose<Exposes>({
    getValue(field: string) {
      return tagRef.value.getValue().then(() => {
        if (!localValue.value) {
          return Promise.reject();
        }
        return {
          [field]: props.single ? localValue.value[0] : localValue.value,
        };
      });
    },
  });
</script>
