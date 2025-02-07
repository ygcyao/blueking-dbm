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
  <SmartAction
    class="apply-riak-page"
    :offset-target="getSmartActionOffsetTarget">
    <DbForm
      ref="formRef"
      auto-label-width
      class="mb-32"
      :model="formData"
      :rules="formRules">
      <DbCard :title="t('业务信息')">
        <BusinessItems
          v-model:app-abbr="formData.details.db_app_abbr"
          v-model:biz-id="formData.bk_biz_id"
          perrmision-action-id="riak_cluster_apply"
          @change-biz="handleChangeBiz" />
        <ModuleItem
          v-model="formData.details.db_module_id"
          v-model:module-alias-name="moduleAliasName"
          :biz-id="formData.bk_biz_id"
          :cluster-type="ClusterTypes.RIAK" />
        <ClusterName v-model="formData.details.cluster_name" />
        <ClusterAlias
          v-model="formData.details.cluster_alias"
          :biz-id="formData.bk_biz_id"
          cluster-type="riak" />
        <CloudItem
          v-model="formData.details.bk_cloud_id"
          @change="handleChangeCloud" />
      </DbCard>
      <RegionItem
        ref="regionItemRef"
        v-model="formData.details.city_code" />
      <DbCard :title="t('数据库部署信息')">
        <BkFormItem
          :label="t('Riak版本')"
          property="details.db_version"
          required>
          <BkSelect
            v-model="formData.details.db_version"
            class="item-input"
            disabled
            :input-search="false"
            style="width: 185px">
            <BkOption
              v-for="item in dbVersionList"
              :key="item"
              :label="item"
              :value="item" />
          </BkSelect>
        </BkFormItem>
        <!-- <BkFormItem
          :label="t('访问端口')"
          property="details.http_port"
          required>
          <BkInput
            v-model="formData.details.http_port"
            disabled
            style="width: 185px;"
            type="number" />
        </BkFormItem> -->
      </DbCard>
      <DbCard :title="t('部署需求')">
        <BkFormItem
          :label="t('服务器选择')"
          property="details.ip_source"
          required>
          <BkRadioGroup v-model="formData.details.ip_source">
            <BkRadioButton label="resource_pool">
              {{ t('自动从资源池匹配') }}
            </BkRadioButton>
            <BkRadioButton label="manual_input">
              {{ t('业务空闲机') }}
            </BkRadioButton>
          </BkRadioGroup>
        </BkFormItem>
        <Transition
          mode="out-in"
          name="dbm-fade">
          <div
            v-if="formData.details.ip_source === 'resource_pool'"
            class="mb-24">
            <BkFormItem
              :label="t('资源规格')"
              property="spec_id"
              required>
              <SpecSelector
                ref="specRef"
                v-model="formData.spec_id"
                :biz-id="formData.bk_biz_id"
                :city="formData.details.city_code"
                :cloud-id="formData.details.bk_cloud_id"
                :cluster-type="ClusterTypes.RIAK"
                machine-type="riak"
                style="width: 435px" />
            </BkFormItem>
            <BkFormItem
              :label="t('节点数量')"
              property="nodes_num"
              required>
              <BkInput
                v-model="formData.nodes_num"
                clearable
                :min="3"
                show-clear-only-hover
                style="width: 185px"
                type="number" />
            </BkFormItem>
          </div>
          <div
            v-else
            class="mb-24">
            <BkFormItem
              ref="nodesRef"
              :label="t('服务器')"
              property="details.nodes"
              required>
              <IpSelector
                :biz-id="formData.bk_biz_id"
                :cloud-info="cloudInfo"
                :data="formData.details.nodes"
                :disable-dialog-submit-method="disableHostSubmitMethods"
                :os-types="[OSTypes.Linux]"
                @change="handleProxyIpChange">
                <template #desc>
                  {{ t('至少n台', { n: 3 }) }}
                </template>
                <template #submitTips="{ hostList }">
                  <I18nT
                    keypath="至少n台_已选n台"
                    style="font-size: 14px; color: #63656e"
                    tag="span">
                    <span style="font-weight: bold; color: #2dcb56"> 3 </span>
                    <span style="font-weight: bold; color: #3a84ff"> {{ hostList.length }} </span>
                  </I18nT>
                </template>
              </IpSelector>
            </BkFormItem>
          </div>
        </Transition>
        <BkFormItem :label="t('备注')">
          <BkInput
            v-model="formData.remark"
            :maxlength="100"
            :placeholder="t('请提供更多有用信息申请信息_以获得更快审批')"
            style="width: 655px"
            type="textarea" />
        </BkFormItem>
      </DbCard>
    </DbForm>
    <template #action>
      <div>
        <BkButton
          :loading="baseState.isSubmitting"
          style="width: 88px"
          theme="primary"
          @click="handleSubmit">
          {{ t('提交') }}
        </BkButton>
        <BkButton
          class="ml8 w-88"
          :disabled="baseState.isSubmitting"
          @click="handleReset">
          {{ t('重置') }}
        </BkButton>
        <BkButton
          class="ml8 w-88"
          :disabled="baseState.isSubmitting"
          @click="handleCancel">
          {{ t('取消') }}
        </BkButton>
      </div>
    </template>
  </SmartAction>
</template>
<script setup lang="ts">
  import InfoBox from 'bkui-vue/lib/info-box';
  import { useI18n } from 'vue-i18n';

  import type { BizItem, HostInfo } from '@services/types';

  import { useApplyBase } from '@hooks';

  import { ClusterTypes, OSTypes, TicketTypes } from '@common/const';

  import IpSelector from '@components/ip-selector/IpSelector.vue';

  import BusinessItems from '@views/db-manage/common/apply-items/BusinessItems.vue';
  import CloudItem from '@views/db-manage/common/apply-items/CloudItem.vue';
  import ClusterAlias from '@views/db-manage/common/apply-items/ClusterAlias.vue';
  import ClusterName from '@views/db-manage/common/apply-items/ClusterName.vue';
  import ModuleItem from '@views/db-manage/common/apply-items/ModuleItem.vue';
  import RegionItem from '@views/db-manage/common/apply-items/RegionItem.vue';
  import SpecSelector from '@views/db-manage/common/apply-items/SpecSelector.vue';

  // 目前固定为此版本
  const dbVersionList = [2.2];

  const genDefaultFormData = () => ({
    bk_biz_id: '' as number | '',
    remark: '',
    ticket_type: TicketTypes.RIAK_CLUSTER_APPLY,
    spec_id: '' as number | '',
    nodes_num: 3,
    details: {
      bk_cloud_id: 0,
      db_app_abbr: '',
      ip_source: 'resource_pool',
      db_module_id: null as number | null,
      cluster_name: '',
      cluster_alias: '',
      city_code: '',
      db_version: '2.2',
      nodes: [] as HostInfo[],
      // http_port: 8087,
    },
  });

  const route = useRoute();
  const router = useRouter();
  const { t } = useI18n();
  const { baseState, bizState, handleCreateAppAbbr, handleCreateTicket, handleCancel } = useApplyBase();

  const formRef = ref();
  const specRef = ref();
  const nodesRef = ref();
  const cloudInfo = ref({
    id: '' as number | string,
    name: '',
  });
  const moduleAliasName = ref('');
  const formData = reactive(genDefaultFormData());

  const formRules = {
    nodes_num: [
      {
        validator: (value: number) => value >= 3,
        message: t('节点数至少为n台', [3]),
        trigger: 'change',
      },
    ],
    'details.nodes': [
      {
        validator: (value: HostInfo[]) => value.length >= 3,
        message: t('节点数至少为n台', [3]),
        trigger: 'change',
      },
    ],
  };

  const getSmartActionOffsetTarget = () => document.querySelector('.bk-form-content');

  // 切换业务，需要重置 IP 相关的选择
  const handleChangeBiz = (info: BizItem) => {
    bizState.info = info;
    bizState.hasEnglishName = !!info.english_name;
  };

  const handleChangeCloud = (info: { id: number | string; name: string }) => {
    cloudInfo.value = info;

    formData.details.nodes = [];
  };

  const disableHostSubmitMethods = (hostList: Array<HostInfo[]>) =>
    hostList.length < 3 ? t('至少n台', { n: 3 }) : false;

  const handleProxyIpChange = (data: HostInfo[]) => {
    formData.details.nodes = data;
    if (formData.details.nodes.length > 0) {
      nodesRef.value.clearValidate();
    }
  };

  const handleSubmit = () => {
    formRef.value.validate().then(() => {
      baseState.isSubmitting = true;

      const params = {
        ...formData,
        details: {
          ...formData.details,
          db_module_name: moduleAliasName.value,
        },
      };

      if (formData.details.ip_source === 'resource_pool') {
        Object.assign(params.details, {
          resource_spec: {
            riak: {
              count: formData.nodes_num,
              spec_id: formData.spec_id,
              ...specRef.value.getData(),
            },
          },
        });
      } else {
        Object.assign(params.details, {
          nodes: {
            riak: formData.details.nodes.map((nodeItem) => ({
              ip: nodeItem.ip,
              bk_host_id: nodeItem.host_id,
              bk_cloud_id: nodeItem.cloud_id,
            })),
          },
        });
      }

      // 若业务没有英文名称则先创建业务英文名称再创建单据，否则直接创建单据
      bizState.hasEnglishName ? handleCreateTicket(params) : handleCreateAppAbbr(params);
    });
  };

  const handleReset = () => {
    InfoBox({
      title: t('确认重置表单内容'),
      content: t('重置后_将会清空当前填写的内容'),
      cancelText: t('取消'),
      onConfirm: () => {
        Object.assign(formData, genDefaultFormData());
        formRef.value.clearValidate();
        nextTick(() => {
          window.changeConfirm = false;
        });
        return true;
      },
    });
  };

  defineExpose({
    routerBack() {
      if (!route.query.from) {
        router.back();
        return;
      }
      router.push({
        name: route.query.from as string,
      });
    },
  });
</script>

<style lang="less">
  .apply-riak-page {
    display: block;

    .db-card {
      & ~ .db-card {
        margin-top: 20px;
      }
    }

    .item-input {
      width: 435px;
    }
  }
</style>
