<template>
  <RouterLink
    v-if="isShowRaw"
    v-bind="{ ...($attrs as unknown as any) }">
    <slot />
  </RouterLink>
  <span
    v-else
    v-cursor
    class="auth-router-link-disabled"
    :loading="loading"
    v-bind="{
      class: attrs.class,
      style: attrs.style as StyleValue,
    }"
    @click.stop="handleRequestPermission">
    <slot />
  </span>
</template>
<script setup lang="ts">
  import { type StyleValue, useAttrs } from 'vue';

  import useBase from './use-base';

  /* eslint-disable vue/no-unused-properties */
  interface Props {
    permission?: boolean | string;
    actionId: string;
    resource?: string | number;
    bizId?: string | number;
  }

  const props = withDefaults(defineProps<Props>(), {
    permission: 'normal',
    resource: '',
    bizId: undefined,
  });

  defineOptions({
    inheritAttrs: false,
  });

  const attrs = useAttrs();
  const { loading, isShowRaw, handleRequestPermission } = useBase(props);
</script>
<style lang="less" scoped>
  .auth-router-link-disabled {
    color: #c4c6cc !important;
    user-select: none !important;
  }
</style>
