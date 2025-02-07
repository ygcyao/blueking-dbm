/*
 * TencentBlueKing is pleased to support the open source community by making 蓝鲸智云-DB管理系统(BlueKing-BK-DBM) available.
 *
 * Copyright (C) 2017-2023 THL A29 Limited, a Tencent company. All rights reserved.
 *
 * Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at https://opensource.org/licenses/MIT
 *
 * Unless required by applicable law or agreed to in writing, software distributed under the License is distributed
 * on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for
 * the specific language governing permissions and limitations under the License.
 */

import type { App } from 'vue';
import { VxeTooltip } from 'vxe-pc-ui';

import AuthButton from '@components/auth-component/button.vue';
import AuthTemplate from '@components/auth-component/component.vue';
import AuthOption from '@components/auth-component/option.vue';
import AuthRouterLink from '@components/auth-component/router-link.vue';
import AuthSwitch from '@components/auth-component/switch.vue';
import DbCard from '@components/db-card/index.vue';
import DbForm from '@components/db-form/index.vue';
import DbFormItem from '@components/db-form/item.vue';
import DbIcon from '@components/db-icon';
import DbPopconfirm from '@components/db-popconfirm/index.vue';
import DbSearchSelect from '@components/db-search-select/index.vue';
import DbSideslider from '@components/db-sideslider/index.vue';
import DbStatus from '@components/db-status/index.vue';
import DbTable from '@components/db-table/index.vue';
import DbOriginalTable from '@components/db-table/OriginalTable.vue';
import DbTextarea from '@components/db-textarea/DbTextarea.vue';
import FunController from '@components/function-controller/FunController.vue';
import MoreActionExtend from '@components/more-action-extend/Index.vue';
import ScrollFaker from '@components/scroll-faker/Index.vue';
import SkeletonLoading from '@components/skeleton-loading/Index.vue';
import SmartAction from '@components/smart-action/Index.vue';
import { ipSelector } from '@components/vue2/ip-selector';

import { Table, TableColumn } from '@blueking/table';
import UserSelector from '@patch/user-selector/selector.vue';

import('@blueking/table/vue3/vue3.css');

export const setGlobalComps = (app: App<Element>) => {
  app.component('DbCard', DbCard);
  app.component('DbForm', DbForm);
  app.component('DbFormItem', DbFormItem);
  app.component('DbIcon', DbIcon);
  app.component('DbPopconfirm', DbPopconfirm);
  app.component('DbSearchSelect', DbSearchSelect);
  app.component('DbSideslider', DbSideslider);
  app.component('DbTextarea', DbTextarea);
  app.component('DbTable', DbTable);
  app.component('DbStatus', DbStatus);
  app.component('DbOriginalTable', DbOriginalTable);
  app.component('SmartAction', SmartAction);
  app.component('BkIpSelector', ipSelector);
  app.component('FunController', FunController);
  app.component('MoreActionExtend', MoreActionExtend);
  app.component('UserSelector', UserSelector);
  app.component('ScrollFaker', ScrollFaker);
  app.component('SkeletonLoading', SkeletonLoading);
  app.component('AuthButton', AuthButton);
  app.component('AuthTemplate', AuthTemplate);
  app.component('AuthOption', AuthOption);
  app.component('AuthSwitcher', AuthSwitch);
  app.component('AuthRouterLink', AuthRouterLink);
  setTimeout(() => {
    // eslint-disable-next-line
    delete app._context.components.BkTable;
    // eslint-disable-next-line
    delete app._context.components.BkTableColumn;

    app.component('BkTable', Table);
    app.component('BkTableColumn', TableColumn);
    app.component('VxeTooltip', VxeTooltip);
  });
};
