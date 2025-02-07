<template>
  <BkLoading :loading="isLoading || isCheckoutDbLoading">
    <span
      v-bk-tooltips="{
        content: disabledTips,
        disabled: !Boolean(disabledTips),
      }"
      @click="handleShowEditName">
      <TableEditElement
        ref="elementRef"
        :rules="rules">
        <BkButton
          :disabled="Boolean(disabledTips)"
          text
          theme="primary">
          <span v-if="localRenameInfoList.length < 1">--</span>
          <template v-else>
            <span v-if="hasEditDbName">
              {{ t('已更新') }}
            </span>
            <I18nT
              v-else
              keypath="n项待修改">
              <span style="padding-right: 4px; font-weight: bold; color: #ea3636">
                {{ localRenameInfoList.length }}
              </span>
            </I18nT>
          </template>
        </BkButton>
      </TableEditElement>
    </span>
  </BkLoading>
  <BkSideslider
    v-model:is-show="isShowEditName"
    :width="900">
    <template #header>
      <span>{{ t('手动修改回档的 DB 名') }}</span>
      <BkTag class="ml-8">{{ clusterData?.domain }}</BkTag>
    </template>
    <EditName
      v-if="clusterData && dstClusterData"
      ref="editNameRef"
      :cluster-id="clusterData.id"
      :db-ignore-name="dbIgnoreName"
      :db-name="dbName"
      :rename-info-list="localRenameInfoList"
      :target-cluster-id="dstClusterData.id" />
    <template #footer>
      <BkButton
        class="w-88"
        theme="primary"
        @click="handleSubmit">
        {{ t('保存') }}
      </BkButton>
      <BkButton
        class="w-88 ml-8"
        @click="handleCancel">
        {{ t('取消') }}
      </BkButton>
    </template>
  </BkSideslider>
</template>
<script setup lang="ts">
  import _ from 'lodash';
  import { computed, ref, shallowRef, watch } from 'vue';
  import type { ComponentExposed } from 'vue-component-type-helpers';
  import { useI18n } from 'vue-i18n';
  import { useRequest } from 'vue-request';

  import { checkClusterDatabase } from '@services/source/dbbase';
  import { getSqlserverDbs } from '@services/source/sqlserver';

  import TableEditElement from '@components/render-table/columns/element/Index.vue';

  import EditName, { type IValue } from '@views/db-manage/sqlserver/common/edit-rename-info/Index.vue';

  import { makeMap } from '@utils';

  interface Props {
    clusterData?: {
      id: number;
      domain: string;
    };
    dstClusterData?: {
      id: number;
      domain: string;
    };
  }

  interface Expose {
    getValue: () => Promise<Record<'rename_infos', IValue[]>>;
  }

  const props = defineProps<Props>();

  const dbName = defineModel<string[]>('dbName', {
    required: true,
  });

  const dbIgnoreName = defineModel<string[]>('dbIgnoreName', {
    required: true,
  });

  const { t } = useI18n();

  const elementRef = ref<ComponentExposed<typeof TableEditElement>>();
  const editNameRef = ref<InstanceType<typeof EditName>>();
  const localRenameInfoList = shallowRef<
    {
      db_name: string;
      target_db_name: string;
      rename_db_name: string;
    }[]
  >([]);
  const isShowEditName = ref(false);
  const hasEditDbName = ref(false);

  const disabledTips = computed(() => {
    if (props.clusterData && props.dstClusterData && dbName.value.length > 0) {
      return '';
    }
    return t('请先设置集群、目标集群、构造 DB');
  });

  const rules = [
    {
      validator: () => localRenameInfoList.value.length > 0,
      message: t('构造后 DB 名不能为空'),
    },
    {
      validator: () => hasEditDbName.value,
      message: t('构造后 DB 名待有冲突更新'),
    },
    {
      validator: () => {
        const dbIgnoreNameMap = makeMap(dbIgnoreName.value);
        const dbNameList = dbName.value.filter((item) => !/\*/.test(item) && !/%/.test(item) && !dbIgnoreNameMap[item]);
        return dbNameList.length <= localRenameInfoList.value.length;
      },
      message: t('迁移后 DB 和迁移 DB 数量不匹配'),
    },
  ];

  const { loading: isCheckoutDbLoading, run: runCheckClusterDatabase } = useRequest(checkClusterDatabase, {
    manual: true,
    onSuccess(data) {
      hasEditDbName.value = _.every(Object.values(data), (item) => !item);
    },
  });

  const { loading: isLoading, run: fetchSqlserverDbs } = useRequest(getSqlserverDbs, {
    manual: true,
    onSuccess(data) {
      localRenameInfoList.value = data.map((item) => ({
        db_name: item,
        target_db_name: item,
        rename_db_name: '',
      }));
      if (data.length > 0) {
        runCheckClusterDatabase({
          bk_biz_id: window.PROJECT_CONFIG.BIZ_ID,
          cluster_id: props.dstClusterData!.id,
          db_list: data,
        });
      }
    },
  });

  let isInnerChange = false;
  watch(
    () => [props.clusterData, dbName.value, dbIgnoreName.value],
    () => {
      if (isInnerChange) {
        isInnerChange = false;
        return;
      }
      if (!props.clusterData || !props.dstClusterData || dbName.value.length < 1) {
        localRenameInfoList.value = [];
        return;
      }
      fetchSqlserverDbs({
        cluster_id: props.clusterData.id,
        db_list: dbName.value,
        ignore_db_list: dbIgnoreName.value,
      });
    },
    {
      immediate: true,
    },
  );

  const handleShowEditName = () => {
    isShowEditName.value = true;
  };

  const handleSubmit = () => {
    editNameRef.value!.submit().then((result) => {
      isShowEditName.value = false;
      hasEditDbName.value = true;
      dbName.value = result.dbName;
      dbIgnoreName.value = result.dbIgnoreName;
      localRenameInfoList.value = result.renameInfoList;
      isInnerChange = true;
      elementRef.value!.getValue();
    });
  };

  const handleCancel = () => {
    isShowEditName.value = false;
  };

  defineExpose<Expose>({
    getValue() {
      return elementRef.value!.getValue().then(() => ({
        rename_infos: localRenameInfoList.value,
      }));
    },
  });
</script>
<style lang="less" scoped>
  .render-rename {
    display: flex;
    align-items: center;
    justify-content: center;
  }
</style>
