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
  <div class="domain-table">
    <DbOriginalTable
      :columns="columns"
      :data="tableData"
      :empty-text="t('请选择业务和DB模块名')" />
  </div>
</template>

<script setup lang="tsx">
  import { Form } from 'bkui-vue';
  import type { Column } from 'bkui-vue/lib/table/props';
  import { useI18n } from 'vue-i18n';

  import { nameRegx } from '@common/regex';

  import ClusterIdBatchEdit from './ClusterIdBatchEdit.vue';
  import ClusterNameBatchEdit from './ClusterNameBatchEdit.vue';

  type FormItem = typeof Form.FormItem

  interface Domain {
    [key: string]: string
    domain: string,
    set_id: string,
    name: string,
  }

  interface Props {
    appAbbr: string
    nodesNumber: number
  }

  const props = defineProps<Props>();
  const domains = defineModel<Array<Domain>>('domains', {
    default: () => [],
  });

  const { t } = useI18n();

  const rules = {
    set_id: [
      {
        required: true,
        message: t('必填项'),
        trigger: 'change',
      },
      {
        message: t('最大长度为m', { m: 63 }),
        trigger: 'blur',
        validator: (val: string) => val.length <= 63,
      },
      {
        message: t('以小写英文字母开头_且只能包含英文字母_数字_连字符'),
        trigger: 'blur',
        validator: (val: string) => nameRegx.test(val),
      },
      {
        message: t('集群ID重复'),
        trigger: 'blur',
        validator: (val: string) => clusterIdKeys.value.filter(item => item === val).length < 2,
      },
    ],
    // name: [
    //   {
    //     required: true,
    //     message: t('必填项'),
    //     trigger: 'change',
    //   },
    //   {
    //     message: t('最大长度为m', { m: 63 }),
    //     trigger: 'blur',
    //     validator: (val: string) => val.length <= 63,
    //   },
    //   {
    //     message: t('集群ID重复'),
    //     trigger: 'blur',
    //     validator: (val: string) => clusterNameKeys.value.filter(item => item === val).length < 2,
    //   },
    // ],
  };

  const columns: Column[] = [
    {
      type: 'index',
      label: t('序号'),
      width: 60,
    },
    {
      label: t('主域名'),
      field: 'domain',
      width: 200,
    },
    {
      label: () => (
        <div class='table-custom-label'>
          { t('集群ID') }
          {
            tableData.value.length !== 0 && (
              <span v-bk-tooltips={t('批量录入')}>
                <ClusterIdBatchEdit onChange={value => handleBatchEdit(value, 'set_id')} />
              </span>
            )
          }
          <span class="required-mark ml-4">*</span>
        </div>
      ),
      field: 'set_id',
      minWidth: 300,
      render: ({ index }: { index: number }) => (
        <bk-form-item
          ref={(value: FormItem) => setSetIdRef(value)}
          class="cell-item"
          errorDisplayType="tooltips"
          property={`details.replica_sets.${index}.set_id`}
          key={index}
          rules={rules.set_id}
          label-width={0}>
          <bk-input
            model-value={domains.value[index]?.set_id}
            placeholder={t('请输入')}
            v-bk-tooltips={{
              trigger: 'click',
              placement: 'top',
              theme: 'light',
              content: t('以小写英文字母开头_且只能包含英文字母_数字_连字符'),
            }}
            onInput={(value: string) => handleChangeCellValue(value, index, 'set_id')}
          />
        </bk-form-item>
      ),
    },
    {
      label: () => (
        <div class='table-custom-label'>
          { t('集群名称') }
          {
            tableData.value.length !== 0 && (
              <span v-bk-tooltips={t('批量录入')}>
              <ClusterNameBatchEdit
                onChange={value => handleBatchEdit(value, 'name')} />
              </span>
            )
          }
        </div>
      ),
      field: 'name',
      minWidth: 300,
      render: ({ index }: { index: number }) => (
        <bk-form-item
          ref={(value: FormItem) => setNameRef(value)}
          class="cell-item"
          errorDisplayType="tooltips"
          property={`details.replica_sets.${index}.name`}
          key={index}
          label-width={0}>
          <bk-input
            model-value={domains.value[index]?.name}
            placeholder={t('请输入')}
            onInput={(value: string) => handleChangeCellValue(value, index, 'name')}
          />
        </bk-form-item>
      ),
    },
  ];

  const clusterIdRefs: FormItem[] = [];
  const clusterNameRefs: FormItem[] = [];

  // 没有 appName 则不展示 table 数据
  const tableData = computed(() => {
    if (props.appAbbr) {
      return domains.value;
    }
    return [];
  });
  const clusterIdKeys = computed(() => tableData.value.map(item => item.set_id));
  // const clusterNameKeys = computed(() => tableData.value.map(item => item.name));

  watch(() => props.nodesNumber, () => {
    clusterIdRefs.splice(0, clusterIdRefs.length - 1);
    clusterNameRefs.splice(0, clusterNameRefs.length - 1);
  });

  const setSetIdRef = (el: FormItem) => {
    if (el) {
      clusterIdRefs.push(el);
    }
  };

  const setNameRef = (el: FormItem) => {
    if (el) {
      clusterNameRefs.push(el);
    }
  };

  const generateDomian = (setId: string) => `m1.${setId}.${props.appAbbr}.db`;

  const handleBatchEdit = (values: string[], fieldName: keyof Domain) => {
    if (values.length !== 0) {
      const newDomains = domains.value;
      newDomains.forEach((item, index) => {
        if (values[index] !== undefined) {
          newDomains[index][fieldName] = values[index];

          // 主域名根据集群ID自动生成
          if (fieldName === 'set_id') {
            newDomains[index].domain = generateDomian(values[index]);
          }
        }
      });
      domains.value = newDomains;
      // 校验集群ID信息
      nextTick(() => {
        if (fieldName === 'set_id') {
          clusterIdRefs.forEach(item => item?.validate?.());
        } else {
          clusterNameRefs.forEach(item => item?.validate?.());
        }
      });
    }
  };

  const handleChangeCellValue = (value: string, index: number, fieldName: keyof Domain) => {
    const newDomains = domains.value;
    newDomains[index][fieldName] = value;

    // 主域名根据集群ID自动生成
    if (fieldName === 'set_id') {
      newDomains[index].domain = generateDomian(value);
    }

    domains.value = newDomains;
  };
</script>

<style lang="less" scoped>
  .domain-table {
    :deep(.bk-table) {
      .bk-form-content {
        margin-left: 0 !important;
      }
    }

    :deep(.table-custom-label) {
      display: flex;
      align-items: center;

      .required-mark {
        color: #ea3636;
      }
    }

    :deep(.domain-address) {
      display: flex;
      align-items: center;

      > span {
        flex-shrink: 0;
      }

      .cell-item {
        margin-bottom: 0;

        .bk-form-label {
          display: none;
        }
      }
    }
  }
</style>
