import type { DetailBase, DetailClusters } from '../common';

export interface InstanceProxyClose extends DetailBase {
  clusters: DetailClusters;
  cluster_ids: number[];
}
