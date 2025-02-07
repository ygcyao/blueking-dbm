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
  <div
    class="editabletable-element"
    :class="{
      'is-focused': isFocus,
      'is-error': Boolean(errorMessage),
      'is-disabled': disabled,
    }"
    :disabled="disabled"
    @mouseenter="handleMouseenter"
    @mouseleave="handleMOouseleave">
    <div
      v-if="slots.prepend"
      class="prepend-flag">
      <slot name="prepend" />
    </div>
    <div ref="rootRef">
      <slot />
    </div>
    <div
      v-if="isShowPlaceholder"
      class="placeholder"
      :style="{
        color: '#c4c6cc',
        paddingLeft: slots.prepend ? '18px' : 0,
      }">
      {{ placeholder }}
    </div>
    <div
      v-if="errorMessage"
      class="input-error">
      <DbIcon
        v-bk-tooltips="errorMessage"
        type="exclamation-fill" />
    </div>
    <div
      v-if="slots.append"
      class="append-flag">
      <slot name="append" />
    </div>
    <div
      v-if="value"
      class="value-clear"
      @click.stop="handleClear">
      <DbIcon type="delete-fill" />
    </div>
  </div>
</template>
<script setup lang="ts" generic="T extends any">
  import _ from 'lodash';
  import { nextTick, onMounted, onUpdated, type VNode } from 'vue';

  import useValidtor, { type Rules } from '../../hooks/useValidtor';

  interface Props {
    rules?: Rules;
    value?: any;
    placeholder?: string;
    disabled?: boolean;
  }

  interface Emits {
    (e: 'clear'): void;
  }

  interface Exposes {
    getValue: () => Promise<boolean>;
  }

  const props = withDefaults(defineProps<Props>(), {
    rules: undefined,
    value: '',
    placeholder: '请设置值',
  });

  const emits = defineEmits<Emits>();

  const slots = defineSlots<{
    prepend?: () => VNode | VNode[];
    default: () => VNode | VNode[];
    append?: () => VNode | VNode[];
  }>();

  const { message: errorMessage, validator } = useValidtor(props.rules);

  const rootRef = ref<HTMLElement>();

  const isShowPlaceholder = ref(true);
  const isFocus = ref(false);

  const calcShowPlaceholder = () => {
    nextTick(() => {
      isShowPlaceholder.value = !_.trim(rootRef.value!.innerText);
    });
  };

  const handleMouseenter = () => {
    isFocus.value = true;
  };

  const handleMOouseleave = () => {
    isFocus.value = false;
  };

  const handleClear = () => {
    emits('clear');
  };

  onUpdated(() => {
    calcShowPlaceholder();
  });

  onMounted(() => {
    calcShowPlaceholder();
  });

  defineExpose<Exposes>({
    getValue() {
      return validator(props.value);
    },
  });
</script>
<style lang="less">
  .editabletable-element {
    position: relative;
    display: flex;
    min-height: 42px;
    padding: 10px 16px;
    overflow: hidden;
    line-height: 20px;
    color: #63656e;
    text-overflow: ellipsis;
    white-space: nowrap;
    align-items: center;
    border: 1px solid transparent;

    &:hover {
      .append-flag,
      .value-clear {
        display: flex;
      }
    }

    &.is-error {
      background-color: #fff0f1 !important;
    }

    &.is-focused {
      border: 1px solid #a3c5fd !important;
    }

    &.is-disabled {
      cursor: not-allowed;
      background: #fafbfd;
    }

    .input-error {
      position: absolute;
      top: 0;
      right: 0;
      bottom: 0;
      z-index: 1;
      display: flex;
      padding-right: 10px;
      font-size: 14px;
      color: #ea3636;
      align-items: center;
    }

    .placeholder {
      position: absolute;
      top: 10px;
      right: 20px;
      left: 18px;
      z-index: 1;
      height: 20px;
      overflow: hidden;
      font-size: 12px;
      line-height: 20px;
      color: #c4c6cc;
      text-overflow: ellipsis;
      white-space: nowrap;
      pointer-events: none;
    }

    .prepend-flag {
      display: flex;
      width: 24px;
      height: 100%;
      align-items: center;
    }

    .append-flag {
      position: absolute;
      right: 5px;
      display: none;
      width: 24px;
      height: 40px;
      align-items: center;
      cursor: pointer;
    }

    .value-clear {
      position: absolute;
      right: 5px;
      display: none;
      width: 24px;
      height: 40px;
      color: #c4c6cc;
      cursor: pointer;
      align-items: center;

      &:hover {
        color: #979ba5;
      }
    }
  }
</style>
