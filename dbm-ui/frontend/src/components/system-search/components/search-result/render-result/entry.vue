<template>
  <div>
    <div
      v-for="item in data"
      :key="item.entry"
      class="result-item"
      @click="handleGo(item)">
      <div class="value-text">
        <HightLightText
          :key-word="formattedKeyword"
          :text="item.entry" />
      </div>
      <div class="biz-text">
        {{ bizIdNameMap[item.bk_biz_id] }}
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { systemSearchCache } from '@common/cache';
  import { batchSplitRegex } from '@common/regex';

  import { useRedirect } from '@components/system-search/hooks/useRedirect';

  import HightLightText from './components/HightLightText.vue';

  interface Props {
    keyWord: string;
    data: {
      bk_biz_id: number;
      cluster_type: string;
      id: number;
      immute_domain: string;
      name: string;
      entry: string;
    }[];
    bizIdNameMap: Record<number, string>;
  }

  const props = defineProps<Props>();

  const handleRedirect = useRedirect();

  const formattedKeyword = computed(() =>
    props.keyWord
      .split(batchSplitRegex)
      .map((item) => {
        if (item.includes(':')) {
          return item.split(':')[0];
        }
        return item;
      })
      .join(' '),
  );

  const handleGo = (data: Props['data'][number]) => {
    systemSearchCache.appendItem(data.immute_domain);

    handleRedirect(
      data.cluster_type,
      {
        domain: data.immute_domain,
      },
      data.bk_biz_id,
    );
  };
</script>
