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
  <DbForm
    ref="formRef"
    class="rule-form"
    form-type="vertical"
    :model="formData"
    :rules="rules">
    <BkAlert
      class="mb-16"
      closable
      theme="warning"
      :title="t('修改成功后，不会影响已授权的实例，新增的授权将会按照最新的配置生效')" />
    <BkFormItem
      :label="t('账号名')"
      property="account_id"
      required>
      <BkSelect
        v-model="formData.account_id"
        :clearable="false"
        filterable
        :input-search="false"
        :loading="isLoading">
        <BkOption
          v-for="item of accounts"
          :key="item.account_id"
          :label="item.user"
          :value="item.account_id" />
      </BkSelect>
    </BkFormItem>
    <BkFormItem
      :label="t('访问DB')"
      property="access_db"
      required
      :rules="rules.access_db">
      <BkInput
        v-model="formData.access_db"
        :maxlength="100"
        :placeholder="t('请输入访问DB名_支持 % 通配符_多个使用英文逗号_分号或换行分隔')"
        :rows="4"
        type="textarea" />
    </BkFormItem>
    <BkFormItem
      class="rule-form-item"
      :label="t('权限设置')"
      property="privilege">
      <template #label>
        {{ t('权限设置') }}
        <BkCheckbox
          class="top-check-all"
          :indeterminate="topAllCheckedboxIndeterminate"
          :model-value="topAllCheckedboxValue"
          @change="(value: boolean) => handleTopSelectedAll(value)">
          {{ t('全选') }}
        </BkCheckbox>
      </template>
      <div class="rule-setting-box">
        <BkFormItem label="DML">
          <div class="rule-form-row">
            <BkCheckbox
              class="check-all"
              :indeterminate="getAllCheckedboxIndeterminate('dml')"
              :model-value="getAllCheckedboxValue('dml')"
              @change="(value: boolean) => handleSelectedAll('dml', value)">
              {{ t('全选') }}
            </BkCheckbox>
            <BkCheckboxGroup
              v-model="formData.privilege.dml"
              class="rule-form-checkbox-group">
              <BkCheckbox
                v-for="dmlItem of ruleSettingsConfig.dbOperations.dml"
                :key="dmlItem"
                :label="dmlItem">
                {{ dmlItem }}
              </BkCheckbox>
            </BkCheckboxGroup>
          </div>
        </BkFormItem>
        <BkFormItem label="DDL">
          <div class="rule-form-row">
            <BkCheckbox
              class="check-all"
              :indeterminate="getAllCheckedboxIndeterminate('ddl')"
              :model-value="getAllCheckedboxValue('ddl')"
              @change="(value: boolean) => handleSelectedAll('ddl', value)">
              {{ t('全选') }}
            </BkCheckbox>
            <BkCheckboxGroup
              v-model="formData.privilege.ddl"
              class="rule-form-checkbox-group">
              <BkCheckbox
                v-for="ddlItem of ruleSettingsConfig.dbOperations.ddl"
                :key="ddlItem"
                :label="ddlItem">
                {{ ddlItem }}
                <span
                  v-if="ruleSettingsConfig.ddlSensitiveWords?.includes(ddlItem)"
                  class="sensitive-tip">
                  {{ t('敏感') }}
                </span>
              </BkCheckbox>
            </BkCheckboxGroup>
          </div>
        </BkFormItem>
        <BkFormItem
          class="mb-0"
          :label="t('全局')">
          <div class="rule-form-row">
            <BkCheckbox
              class="check-all"
              :indeterminate="getAllCheckedboxIndeterminate('glob')"
              :model-value="getAllCheckedboxValue('glob')"
              @change="(value: boolean) => handleSelectedAll('glob', value)">
              {{ t('全选') }}
            </BkCheckbox>
            <BkCheckboxGroup
              v-model="formData.privilege.glob"
              class="rule-form-checkbox-group">
              <BkCheckbox
                v-for="globItem of ruleSettingsConfig.dbOperations.glob"
                :key="globItem"
                :label="globItem">
                {{ globItem }}
                <span class="sensitive-tip">{{ t('敏感') }}</span>
              </BkCheckbox>
            </BkCheckboxGroup>
          </div>
        </BkFormItem>
      </div>
    </BkFormItem>
  </DbForm>
</template>

<script setup lang="ts">
  import _ from 'lodash';
  import { useI18n } from 'vue-i18n';
  import { useRequest } from 'vue-request';

  import { getPermissionRules, queryAccountRules } from '@services/source/mysqlPermissionAccount';
  import type {
    AccountRule,
    AccountRulePrivilege,
    AccountRulePrivilegeKey,
    PermissionRuleAccount,
  } from '@services/types/permission';

  import type { AccountTypes } from '@common/const';

  interface Props {
    isEdit: boolean;
    accountType: AccountTypes;
    ruleSettingsConfig: {
      dbOperations: AccountRulePrivilege;
      ddlSensitiveWords: string[];
    };
    rulesFormData: {
      beforeChange: AccountRule;
      afterChange: AccountRule;
    };
  }

  interface Exposes {
    getValue: () => Promise<{
      userName: string;
      accountRule: AccountRule;
    }>;
  }

  const props = defineProps<Props>();

  const { t } = useI18n();

  const formRef = ref();
  const formData = reactive<AccountRule>({
    account_id: null,
    access_db: '',
    privilege: {
      ddl: [],
      dml: [],
      glob: [],
    },
  });
  const accounts = ref<PermissionRuleAccount[]>([]);
  const existDBs = ref<string[]>([]);

  const rules = {
    privilege: [
      {
        trigger: 'change',
        message: t('请设置权限'),
        validator: () => {
          const { ddl, dml, glob } = formData.privilege;
          return ddl.length !== 0 || dml.length !== 0 || glob.length !== 0;
        },
      },
    ],
    access_db: [
      {
        required: true,
        trigger: 'blur',
        message: t('访问 DB 不能为空'),
        validator: (value: string) => {
          const dbs = value.split(/[\n;,]/);
          return _.every(dbs, (item) => !!item.trim());
        },
      },
      {
        required: true,
        trigger: 'blur',
        message: t('编辑时只能单个，且不能有分隔符'),
        validator: (value: string) => {
          if (props.isEdit) {
            return !new RegExp(/\n|;/g).test(value);
          }
          return true;
        },
      },
      {
        required: true,
        trigger: 'blur',
        message: t('不允许为 *'),
        validator: (value: string) => {
          const dbs = value.split(/[\n;,]/);
          return _.every(dbs, (item) => (!item ? true : !/^\*$/.test(item)));
        },
      },
      {
        required: true,
        trigger: 'blur',
        message: t('% 不能单独使用'),
        validator: (value: string) => {
          const dbs = value.split(/[\n;,]/);
          return _.every(dbs, (item) => (!item ? true : /^(?!%$).+$/.test(item)));
        },
      },
      {
        required: true,
        trigger: 'blur',
        message: t('访问 DB 名必须合法'),
        validator: (value: string) => {
          const dbs = value.split(/[\n;,]/);
          return _.every(dbs, (item) =>
            !item
              ? true
              : /^[a-zA-Z0-9%]([a-zA-Z0-9_%-])*[a-zA-Z0-9%]$/.test(item) && /^(?!stage_truncate).*/.test(item),
          );
        },
      },
      {
        required: true,
        trigger: 'blur',
        message: () => t('该账号下已存在xx规则', [existDBs.value.join(',')]),
        validator: async () => {
          existDBs.value = [];
          const user = accounts.value.find((item) => item.account_id === formData.account_id)?.user;
          if (props.rulesFormData.beforeChange.access_db === formData.access_db) {
            return true;
          }
          const dbs = formData.access_db
            .replace(/\n|;/g, ',')
            .split(',')
            .filter((db) => db);

          if (!user || dbs.length === 0) {
            return false;
          }

          const { results } = await queryAccountRules({
            user,
            access_dbs: dbs,
            account_type: props.accountType,
          });
          const intersection =
            results
              .find((item) => item.account.user === user)
              ?.rules.filter((ruleItem) => dbs.includes(ruleItem.access_db)) || [];
          existDBs.value = intersection.map((item) => item.access_db);
          return !intersection.length;
        },
      },
    ],
  };

  const getAllCheckedboxValue = (key: AccountRulePrivilegeKey) =>
    formData.privilege[key].length === props.ruleSettingsConfig.dbOperations[key].length;

  const topAllCheckedboxValue = computed(() =>
    (['ddl', 'dml', 'glob'] as AccountRulePrivilegeKey[]).every(getAllCheckedboxValue),
  );

  const getAllCheckedboxIndeterminate = (key: AccountRulePrivilegeKey) =>
    formData.privilege[key].length > 0 &&
    formData.privilege[key].length !== props.ruleSettingsConfig.dbOperations[key].length;

  const topAllCheckedboxIndeterminate = computed(() =>
    (['ddl', 'dml', 'glob'] as AccountRulePrivilegeKey[]).some(getAllCheckedboxIndeterminate),
  );

  const { run: getPermissionRulesRun, loading: isLoading } = useRequest(getPermissionRules, {
    manual: true,
    onSuccess({ results }) {
      accounts.value = results.map((item) => item.account);
    },
  });

  watch(
    () => props.rulesFormData,
    () => {
      const sourceData = props.rulesFormData.afterChange.account_id
        ? props.rulesFormData.afterChange
        : props.rulesFormData.beforeChange;
      _.merge(formData, _.cloneDeep(sourceData));
    },
    { immediate: true },
  );

  const handleSelectedAll = (key: AccountRulePrivilegeKey, value: boolean) => {
    formData.privilege[key] = value ? [...props.ruleSettingsConfig.dbOperations[key]] : [];
  };

  const handleTopSelectedAll = (value: boolean) => {
    formData.privilege = value ? _.cloneDeep(props.ruleSettingsConfig.dbOperations) : { ddl: [], dml: [], glob: [] };
  };

  getPermissionRulesRun({
    offset: 0,
    limit: -1,
    bk_biz_id: window.PROJECT_CONFIG.BIZ_ID,
    account_type: props.accountType,
  });

  defineExpose<Exposes>({
    getValue: () =>
      formRef.value.validate().then(() => ({
        userName: accounts.value.find((item) => item.account_id === formData.account_id)?.user || '',
        accountRule: formData,
      })),
  });
</script>

<style lang="less" scoped>
  .rule-form {
    padding: 18px 24px;

    .rule-setting-box {
      padding: 16px 0 16px 16px;
      background: #f5f7fa;
      border-radius: 2px;
    }

    .rule-form-item {
      :deep(.bk-form-label) {
        font-weight: bold;
        color: @title-color;

        &::after {
          position: absolute;
          top: 0;
          width: 14px;
          line-height: 24px;
          color: @danger-color;
          text-align: center;
          content: '*';
        }
      }
    }

    .rule-form-row {
      display: flex;
      width: 100%;
      align-items: flex-start;

      .rule-form-checkbox-group {
        display: flex;
        flex: 1;
        flex-wrap: wrap;

        .bk-checkbox {
          min-width: 33.33%;
          margin-bottom: 16px;
          margin-left: 0;

          .sensitive-tip {
            height: 16px;
            padding: 0 4px;
            font-size: 10px;
            line-height: 16px;
            color: #fe9c00;
            text-align: center;
            background: #fff3e1;
            border-radius: 2px;
          }
        }
      }

      .check-all {
        position: relative;
        width: 48px;
        margin-right: 48px;

        :deep(.bk-checkbox-label) {
          word-break: keep-all;
        }

        &::after {
          position: absolute;
          top: 50%;
          right: -24px;
          width: 1px;
          height: 14px;
          background-color: #c4c6cc;
          content: '';
          transform: translateY(-50%);
        }
      }
    }

    :deep(.bk-form-label) {
      .top-check-all {
        position: absolute;
        right: 0;
      }
    }
  }
</style>
