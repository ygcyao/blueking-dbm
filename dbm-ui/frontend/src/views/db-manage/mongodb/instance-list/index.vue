<template>
  <StretchLayout
    :left-width="368"
    name="instanceViewList">
    <template #list>
      <List v-model:instance-data="instanceData" />
    </template>
    <template
      v-if="instanceData"
      #right>
      <Detail :instance-data="instanceData" />
    </template>
  </StretchLayout>
</template>

<script setup lang="ts">
  import StretchLayout from '@components/stretch-layout/StretchLayout.vue';

  import Detail from './detail/index.vue';
  import List from './list/index.vue';

  const instanceData = ref<{
    instanceAddress: string;
    clusterId: number;
  }>();
</script>
