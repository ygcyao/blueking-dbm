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
  <BkSideslider
    :before-close="handleClose"
    class="rotate-setting-edit-rule"
    :is-show="isShow"
    render-directive="if"
    :width="960"
    @closed="handleClose">
    <template #header>
      <span>
        {{ titleMap[pageType] }}
        <BkTag theme="info">
          {{ t('平台') }}
        </BkTag>
      </span>
    </template>
    <div class="rotation-edit-rule">
      <BkForm
        ref="formRef"
        form-type="vertical"
        :model="formModel"
        :rules="formRules">
        <BkFormItem
          :label="t('规则名称')"
          property="ruleName"
          required>
          <BkInput v-model="formModel.ruleName" />
        </BkFormItem>
      </BkForm>
      <div class="name-tip">
        {{ nameTip }}
      </div>
      <div class="title-spot item-title">{{ t('轮值方式') }}<span class="required" /></div>
      <BkRadioGroup
        v-model="rotateType"
        type="card">
        <BkRadioButton
          v-for="(item, index) in rotateTypeList"
          :key="index"
          :label="item.value">
          {{ item.label }}
        </BkRadioButton>
      </BkRadioGroup>
      <div class="title-spot item-title mt-24">{{ t('轮值业务') }}<span class="required" /></div>
      <RotateBizs
        ref="rotateBizsRef"
        :data="data" />
      <KeepAlive>
        <CycleRotate
          v-if="rotateType === 'handoff'"
          ref="cycleRef"
          :data="data" />
        <CustomRotate
          v-else
          ref="customRef"
          :data="data" />
      </KeepAlive>
    </div>
    <template #footer>
      <BkButton
        class="mr-8"
        :loading="isCreateLoading || isUpdateLoading"
        theme="primary"
        @click="handleConfirm">
        {{ t('确定') }}
      </BkButton>
      <BkButton
        :disabled="isCreateLoading || isUpdateLoading"
        @click="handleClose">
        {{ t('取消') }}
      </BkButton>
    </template>
  </BkSideslider>
</template>

<script setup lang="tsx">
  import { useI18n } from 'vue-i18n';
  import { useRequest } from 'vue-request';

  import DutyRuleModel from '@services/model/monitor/duty-rule';
  import { createDutyRule, updateDutyRule } from '@services/source/monitor';

  import { useBeforeClose } from '@hooks';

  import { messageSuccess } from '@utils';

  import CustomRotate from './CustomRotate.vue';
  import CycleRotate from './CycleRotate.vue';
  import RotateBizs from './RotateBizs.vue';

  interface Props {
    dbType: string;
    data?: DutyRuleModel;
    pageType?: string;
    existedNames?: string[];
  }

  interface Emits {
    (e: 'success'): void;
  }

  const props = withDefaults(defineProps<Props>(), {
    pageType: 'create',
    data: undefined,
    existedNames: () => [],
  });
  const emits = defineEmits<Emits>();
  const isShow = defineModel<boolean>();

  const { t } = useI18n();
  const handleBeforeClose = useBeforeClose();

  const nameTip = ref('');
  const rotateType = ref('handoff');
  const customRef = ref();
  const cycleRef = ref();
  const formRef = ref();
  const rotateBizsRef = ref<InstanceType<typeof RotateBizs>>();
  const formModel = reactive({
    ruleName: '',
  });

  const isCreate = computed(() => props.pageType !== 'edit');

  const titleMap = {
    create: t('新建规则'),
    edit: t('编辑规则'),
    clone: t('克隆规则'),
  } as Record<string, string>;

  const rotateTypeList = [
    {
      value: 'handoff',
      label: t('周期轮值'),
    },
    {
      value: 'regular',
      label: t('自定义轮值'),
    },
  ];

  const formRules = {
    ruleName: [
      {
        validator: (value: string) => {
          if (value.length > 80) {
            return false;
          }
          return true;
        },
        message: t('不能超过n个字符', { n: 80 }),
        trigger: 'blur',
      },
      {
        validator: (value: string) => {
          if (props.pageType === 'clone' && props.data && value === props.data.name) {
            // 克隆才需要校验
            return false;
          }
          return true;
        },
        message: t('规则名称与原规则名称相同'),
        trigger: 'blur',
      },
      // TODO: 以后看情况是否增加接口支持，暂时先用当前页做冲突检测
      {
        validator: async (value: string) => {
          if (['clone', 'create'].includes(props.pageType)) {
            return props.existedNames.every((item) => item !== value);
          }
          return true;
        },
        message: t('规则名称重复'),
        trigger: 'blur',
      },
    ],
  };

  const { loading: isCreateLoading, run: runCreateDutyRule } = useRequest(createDutyRule, {
    manual: true,
    onSuccess: () => {
      messageSuccess(t('保存成功'));
      emits('success');
      isShow.value = false;
    },
  });

  const { loading: isUpdateLoading, run: runUpdateDutyRule } = useRequest(updateDutyRule, {
    manual: true,
    onSuccess: () => {
      // 成功
      messageSuccess(t('编辑成功'));
      emits('success');
      isShow.value = false;
    },
  });

  watch(
    () => [props.pageType, props.data],
    () => {
      if (props.pageType !== 'create' && props.data) {
        // 编辑或者克隆
        formModel.ruleName = props.data.name;
        rotateType.value = props.data.category;
        return;
      }
      formModel.ruleName = '';
    },
  );

  // 点击确定
  const handleConfirm = async () => {
    await formRef.value.validate();
    const bizConfig = await rotateBizsRef.value!.getValue();
    if (rotateType.value === 'handoff') {
      const cycleValues = await cycleRef.value.getValue();
      const cycleParams = {
        name: formModel.ruleName,
        priority: 1,
        db_type: props.dbType,
        category: rotateType.value,
        effective_time: cycleValues.effective_time,
        end_time: cycleValues.end_time,
        duty_arranges: cycleValues.duty_arranges,
        ...bizConfig,
      };
      if (isCreate.value) {
        // 新建/克隆
        runCreateDutyRule(cycleParams);
      } else {
        // 克隆或者编辑
        if (props.data) {
          cycleParams.effective_time = cycleValues.effective_time;
          cycleParams.end_time = cycleValues.end_time;
          runUpdateDutyRule(props.data.id, cycleParams);
        }
      }
    } else {
      // 自定义轮值
      const customValues = await customRef.value.getValue();
      const customParams = {
        name: formModel.ruleName,
        priority: 2,
        db_type: props.dbType,
        category: 'regular',
        effective_time: customValues.effective_time,
        end_time: customValues.end_time,
        duty_arranges: customValues.duty_arranges,
        ...bizConfig,
      };
      if (isCreate.value) {
        // 新建/克隆
        runCreateDutyRule(customParams);
      } else {
        // 克隆或者编辑
        if (props.data) {
          runUpdateDutyRule(props.data.id, customParams);
        }
      }
    }
  };

  async function handleClose() {
    const result = await handleBeforeClose();

    if (!result) {
      return false;
    }
    window.changeConfirm = false;
    isShow.value = false;
    return true;
  }
</script>

<style lang="less" scoped>
  .rotate-setting-edit-rule {
    :deep(.bk-sideslider-footer) {
      box-shadow: none;
    }
  }

  .rotation-edit-rule {
    display: flex;
    width: 100%;
    padding: 24px 40px;
    flex-direction: column;

    .item-title {
      margin-bottom: 6px;
      font-weight: normal;
      color: #63656e;
    }

    .name-tip {
      height: 20px;
      margin-bottom: 6px;
      font-size: 12px;
      color: #ea3636;
    }
  }
</style>
