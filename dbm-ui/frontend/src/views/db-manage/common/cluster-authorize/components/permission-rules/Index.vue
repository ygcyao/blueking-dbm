<template>
  <BkFormItem
    class="cluster-authorize-bold"
    :label="t('权限规则')"
    :property="property"
    required
    :rules="rules">
    <div class="permission-item">
      <BkButton
        class="cluster-authorize-button"
        @click="handleShowAccoutRules">
        <DbIcon
          class="button-icon"
          type="db-icon-add" />
        {{ t('添加账号规则') }}
      </BkButton>
      <BkButton
        v-if="selectedList.length > 0"
        text
        theme="primary"
        @click="handleDeleteAll">
        <DbIcon type="delete" />
        <span class="ml-6">{{ t('全部清空') }}</span>
      </BkButton>
    </div>
    <AccountRulesTable
      v-if="selectedList.length > 0"
      :account-type="accountType"
      class="mt-16"
      :selected-list="selectedList"
      @delete="handleRowDelete" />
  </BkFormItem>
  <AccountRulesSelector
    v-model:is-show="accoutRulesShow"
    :account-type="accountType"
    :selected-list="selectedList"
    @change="handleAccountRulesChange" />
</template>

<script
  setup
  lang="ts"
  generic="
    T extends {
      account: PermissionRule['account'];
      rules: PermissionRule['rules'];
      isNew: boolean;
    }
  ">
  import { useI18n } from 'vue-i18n';

  import type { PermissionRule } from '@services/types';

  import { AccountTypes } from '@common/const';

  import AccountRulesSelector from './components/accounter-rules-selector/Index.vue';
  import AccountRulesTable from './components/accout-rules-preview-table/Index.vue';

  interface Props {
    accountType: AccountTypes;
    property: string;
  }

  defineProps<Props>();

  const modelValue = defineModel<
    {
      user: string;
      rules: PermissionRule['rules'];
    }[]
  >('modelValue', {
    default: () => [],
  });

  const { t } = useI18n();

  const accoutRulesShow = ref(false);
  const selectedList = shallowRef<T[]>([]);

  const rules = [
    {
      trigger: 'change',
      message: t('请添加账号规则'),
      validator: (value: T[]) => value.length > 0,
    },
  ];

  const handleShowAccoutRules = () => {
    accoutRulesShow.value = true;
  };

  const handleAccountRulesChange = (value: T[]) => {
    selectedList.value = value;
    if (value.length > 0) {
      modelValue.value = value.map((item) => ({
        user: item.account.user,
        rules: item.rules,
      }));
    }
  };

  const handleRowDelete = (value: T[]) => {
    selectedList.value = value;
  };

  const handleDeleteAll = () => {
    selectedList.value = [];
  };

  watch(
    modelValue,
    () => {
      selectedList.value = modelValue.value.map((item) => ({
        account: {
          user: item.user,
        },
        rules: item.rules,
      })) as T[];
    },
    {
      immediate: true,
    },
  );
</script>

<style lang="less" scoped>
  .permission-item {
    display: flex;
    justify-content: space-between;

    i {
      font-size: 16px;
    }
  }
</style>
