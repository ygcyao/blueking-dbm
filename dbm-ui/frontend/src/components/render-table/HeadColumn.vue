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
  <th
    ref="columnRef"
    class="ediatable-head-column"
    :class="{
      [`column-${columnKey}`]: true,
      'toolbox-right-fixed-column': isMinimize && isFixedRight && !isScrollToRight,
      'toolbox-left-fixed-column': isMinimize && isFixedLeft && !isScrollToLeft,
    }"
    :data-fixed="fixed"
    :data-maxWidth="maxWidth"
    :data-minWidth="finalMinWidth"
    :data-width="width"
    :style="styles"
    @mousedown="handleMouseDown"
    @mousemove="handleMouseMove">
    <div :class="{ 'edit-required': required }">
      <div
        v-overflow-tips
        class="th-cell">
        <slot />
      </div>
      <div
        v-if="slots.append"
        style="display: inline-block; line-height: 40px; vertical-align: top">
        <slot name="append" />
      </div>
    </div>
  </th>
</template>
<script setup lang="ts">
  import { computed, inject, type StyleValue } from 'vue';

  import { random } from '@utils';

  import { useResizeObserver } from '@vueuse/core';

  import { renderTablekey } from './Index.vue';

  interface Props {
    width?: number;
    required?: boolean;
    minWidth?: number;
    maxWidth?: number;
    fixed?: 'right' | 'left';
  }

  interface Slots {
    append: any;
    default: any;
  }

  const props = withDefaults(defineProps<Props>(), {
    width: undefined,
    required: true,
    minWidth: undefined,
    maxWidth: undefined,
    fixed: undefined,
  });

  const slots = defineSlots<Slots>();

  const { rowWidth, isOverflow: isMinimize, isScrollToLeft, isScrollToRight } = inject(renderTablekey)!;
  const parentTable = inject('toolboxRenderTableKey', {} as any);

  const columnRef = ref();
  const currentWidth = ref(0); // 列拖动后的最新宽度

  const columnKey = random();

  let initWidthRate = 0;
  let isDragedSelf = false;

  const finalMinWidth = computed(() => (props.minWidth ? props.minWidth : props.width));
  const isFixedRight = computed(() => props.fixed === 'right');
  const isFixedLeft = computed(() => props.fixed === 'left');
  const styles = computed<StyleValue>(() => {
    if (props.width && rowWidth?.value && finalMinWidth.value) {
      const newWidth = rowWidth.value * initWidthRate;
      if (newWidth !== props.width) {
        // 宽度变化了
        let width = 0;
        if (isMinimize?.value) {
          // eslint-disable-next-line max-len
          if (
            currentWidth.value !== 0 &&
            (currentWidth.value !== finalMinWidth.value || currentWidth.value !== props.width)
          ) {
            width = currentWidth.value;
          } else {
            width = finalMinWidth.value;
          }
        } else if (newWidth > finalMinWidth.value) {
          width = newWidth;
        } else {
          width = finalMinWidth.value;
        }
        return {
          minWidth: `${width}px`,
        };
      }
    }
    return {
      minWidth: props.width ? `${props.width}px` : '120px',
    };
  });

  watch(
    () => [props.width, rowWidth?.value, currentWidth.value],
    ([width, rowWidth, currentWidth]) => {
      if (!isDragedSelf) {
        return;
      }
      if (width && rowWidth && currentWidth && finalMinWidth.value) {
        isDragedSelf = false;
        if (currentWidth !== 0 && (currentWidth !== finalMinWidth.value || currentWidth !== width)) {
          initWidthRate = currentWidth / rowWidth;
        } else {
          initWidthRate = isMinimize?.value ? finalMinWidth.value / rowWidth : width / rowWidth;
        }
      }
    },
    {
      immediate: true,
    },
  );

  useResizeObserver(columnRef, () => {
    if (!isDragedSelf) {
      return;
    }
    const width = parseFloat(columnRef.value.style.width);
    currentWidth.value = width;
  });

  const handleMouseDown = (event: MouseEvent) => {
    isDragedSelf = true;
    parentTable?.columnMousedown(event, {
      columnKey,
      minWidth: finalMinWidth.value,
    });
  };

  const handleMouseMove = (event: MouseEvent) => {
    parentTable?.columnMouseMove(event);
  };
</script>
<style lang="less">
  .ediatable-head-column {
    background: #f0f1f5 !important;
  }
</style>
