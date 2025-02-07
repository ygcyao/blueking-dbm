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

import type { VNode } from 'vue';

import { FlowTypes } from '@services/source/taskflow';

import { getCostTimeDisplay } from '@utils';

import { t } from '@locales/index';

import type { GraphNode } from './utils';

enum NODE_ICON {
  db_resource_pool = 'db-icon-check-search',
  transfer_file = 'db-icon-file',
  actuator_script = 'db-icon-deploy',
}

export const NODE_STATUS_TEXT = {
  FINISHED: '执行成功',
  RUNNING: '执行中',
  FAILED: '执行失败',
  READY: '待执行',
  CREATED: '待执行',
  SKIPPED: '跳过',
  REVOKED: '已终止',
} as Readonly<Record<string, string>>;

interface RenderCollectionItem {
  render: (args: any[]) => VNode;
}
interface RenderCollection {
  empty: RenderCollectionItem;
  round: RenderCollectionItem;
  ractangle: RenderCollectionItem;
}
export type RenderCollectionKey = 'round' | 'ractangle' | 'empty';

export default class GraphRender {
  renderCollection: RenderCollection;

  constructor() {
    this.renderCollection = {
      // empty 渲染
      empty: {
        render: this.renderEmpty,
      },

      // 圆形渲染
      round: {
        render: this.renderRound,
      },

      // 长方形渲染
      ractangle: {
        render: this.renderRactangle,
      },
    };
  }

  render(type: RenderCollectionKey, args: any[] = []) {
    if (Object.prototype.hasOwnProperty.call(this.renderCollection, type)) {
      const vNode = this.renderCollection[type].render.call(this, args);
      const htmlNode = this.vNodeToHtml(vNode);
      return typeof htmlNode === 'string' ? htmlNode : htmlNode.outerHTML;
    }

    return `type [${type}] render not found`;
  }

  renderEmpty(args: any[] = []) {
    const [node] = args;
    return <span data-node-id={node.id}></span>;
  }

  renderRound(args: any[] = []) {
    const node: GraphNode = args[0];
    const { status } = node.data;
    const text = node.data.type === FlowTypes.EmptyStartEvent ? t('始') : t('终');
    const nodeCls = status ? `node-round--${status.toLowerCase()}` : '';
    return (
      <div
        class={['node-round', nodeCls]}
        data-node-id={node.id}>
        <span>{text}</span>
      </div>
    );
  }

  renderRactangle(args: any[] = []) {
    const node: GraphNode = args[0];
    const flowInfo = args[1];
    const {
      component,
      pipeline,
      status,
      updated_at: updatedAt,
      type,
      started_at: startedAt,
      retryable,
      skippable,
      skip,
    } = node.data;

    const activities = pipeline?.activities;
    let isParentFlow = false;
    const abstractNum = {
      success: 0,
      failed: 0,
      running: 0,
    };

    if (activities) {
      const activityList = Object.values(activities);
      isParentFlow = activityList.length > 0;
      activityList.forEach((activity) => {
        if (activity.status === 'FAILED') {
          abstractNum.failed = abstractNum.failed + 1;
        } else if (activity.status === 'FINISHED') {
          abstractNum.success = abstractNum.success + 1;
        } else if (activity.status === 'RUNNING') {
          abstractNum.running = abstractNum.running + 1;
        }
      });
    }

    const getNodeCls = (nodeStatus: string, isSkip: boolean) => {
      if (node.isTodoNode) {
        return 'node-ractangle--todo';
      }
      if (isSkip) {
        return 'node-ractangle--skipped';
      }
      return nodeStatus ? `node-ractangle--${nodeStatus.toLowerCase()}` : '';
    };

    const getNodeStatusText = (isSkip: boolean) => {
      // if (node.isTodoNode) {
      //   return t('待执行');
      // }
      if (isSkip) {
        return t('忽略错误');
      }
      const nodeStatusText = status ? NODE_STATUS_TEXT[status] : '';
      return nodeStatusText ? t(nodeStatusText) : t('待执行');
    };

    const icon =
      component && component.code in NODE_ICON
        ? NODE_ICON[component.code as keyof typeof NODE_ICON]
        : 'db-icon-default-node';
    const nodeCls = getNodeCls(status, skip);
    const createdStatus = status && status.toLowerCase() === 'created';
    const nodeClickType = type === 'ServiceActivity' && !createdStatus ? 'log' : '';
    const isShowTime = status !== 'CREATED' && updatedAt && startedAt && updatedAt - startedAt >= 0;
    const diffSeconds = status === 'RUNNING' ? Math.floor(Date.now() / 1000) - startedAt : updatedAt - startedAt;
    return (
      <div class={['node-ractangle-layout', { 'node-hover': node.children || nodeClickType }]}>
        {node.children ? (
          <div class='node-ractangle-collapse'>
            <i
              class={[
                'bk-dbm-icon node-ractangle-collapse-open',
                node.isExpand ? 'db-icon-minus-fill' : 'db-icon-plus-8',
              ]}
            />
          </div>
        ) : (
          ''
        )}
        <div
          class={['node-ractangle', nodeCls]}
          style={`max-width: calc(100% - ${node.children ? '14px' : 0})`}
          data-node-id={node.id}
          data-evt-type={nodeClickType}>
          <div class='node-ractangle__status'>
            <i class={['node-ractangle__icon', icon]} />
            {status === 'RUNNING' ? <span class='node-ractangle__icon--loading'></span> : ''}
          </div>
          <div class='node-ractangle__content'>
            <div class='node-ractangle__content-left text-overflow'>
              <strong
                class='node-ractangle__name'
                title={node.data.name as string}>
                {node.data.name}
              </strong>
              <p class='node-ractangle__text'>
                {
                  // eslint-disable-next-line no-nested-ternary
                  isParentFlow ? (
                    <span style='color: #63656E'>
                      <span
                        title={t('成功')}
                        style='color: #2DCB56'>
                        {`${abstractNum.success}`}
                      </span>
                      <span style='margin: 0 5px'>/</span>
                      <span
                        title={t('失败')}
                        style='color: #EA3636'>
                        {`${abstractNum.failed}`}
                      </span>
                      <span style='margin: 0 5px'>/</span>
                      <span
                        title={t('执行中')}
                        style='color: #3a84ff'>
                        {`${abstractNum.running}`}
                      </span>
                    </span>
                  ) : (
                    getNodeStatusText(skip)
                  )
                }
              </p>
              {/* <p class="node-ractangle__text">{nodeStatusText ? t(nodeStatusText) : t('待执行')}</p> */}
            </div>
            <span class='node-ractangle__time'>{isShowTime ? getCostTimeDisplay(diffSeconds) : ''}</span>
          </div>

          {flowInfo.status !== 'REVOKED' && node.children === undefined && (
            <div class='node-ractangle__operations'>
              {node.isTodoNode ? (
                <i
                  class='operation-icon db-icon-check  mr-5'
                  v-bk-tooltips={t('人工确认')}
                  data-evt-type='todo'
                />
              ) : (
                ''
              )}
              {status === 'RUNNING' && (
                <i
                  class='operation-icon db-icon-qiangzhizhongzhi'
                  v-bk-tooltips={t('强制失败')}
                  data-evt-type='force-fail'
                />
              )}
              {status === 'FAILED' && skippable ? (
                <i
                  class='operation-icon db-icon-stop mr-4'
                  v-bk-tooltips={t('跳过')}
                  data-evt-type='skipp'
                />
              ) : (
                ''
              )}
              {status === 'FAILED' && retryable ? (
                <i
                  class='operation-icon db-icon-refresh-2 mr-4'
                  v-bk-tooltips={t('失败重试')}
                  data-evt-type='refresh'
                />
              ) : (
                ''
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  private vNodeToHtml(vNode: VNode | string): string | HTMLElement {
    if (typeof vNode === 'string') {
      return vNode;
    }

    const { type, children, props } = vNode;
    if (typeof children === 'string') {
      return children;
    }

    const el = document.createElement(type as string);
    if (props) {
      const keys = Object.keys(props);
      for (const key of keys) {
        if (key === 'class') {
          el.className = props.class || '';
          continue;
        }
        if (key === 'style') {
          el.style.cssText = props.style || '';
          continue;
        }
        el.setAttribute(key, props[key]);
      }
    }

    if (Array.isArray(children)) {
      for (const childVNode of children) {
        el.append(this.vNodeToHtml(childVNode as VNode));
      }
    }

    return el;
  }
}
