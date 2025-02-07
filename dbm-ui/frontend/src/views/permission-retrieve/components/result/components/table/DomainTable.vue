<template>
  <DbOriginalTable
    class="mt-16 mb-24"
    :columns="columns"
    :data="tableData"
    :max-height="tableMaxHeight"
    :pagination="pagination"
    remote-pagination
    @page-limit-change="handleTableLimitChange"
    @page-value-change="handleTableValueChange" />
</template>

<script setup lang="tsx">
  import { useI18n } from 'vue-i18n';

  import { getAccountPrivs } from '@services/source/mysqlPermissionAccount';

  import { useTableMaxHeight } from '@hooks'

  import { AccountTypes } from '@common/const';

  import { isSensitivePriv } from './common/utils'

  interface TableItem {
    ip: string[],
    db: string[],
    immute_domain: string,
    user: string,
    match_ip: string,
    match_db: string,
    priv: string
  }

  interface Props {
    data?: ServiceReturnType<typeof getAccountPrivs>;
    options?: {
      account_type: AccountTypes;
      dbs?: string;
      is_master?: boolean;
    },
    pagination: {
      current: number,
      count: number,
      limit: number,
      limitList: number[],
    }
  }

  interface Emits {
    (e: 'page-limit-change', value: number): void;
    (e: 'page-value-change', value: number): void;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();

  const { t } = useI18n();
  const tableMaxHeight = useTableMaxHeight(530);

  const columns = computed(() => {
    const domainColumns = [
      {
        label: t('匹配的规则'),
        children: [
          {
            label: t('集群域名'),
            field: 'immute_domain',
            width: 240,
            rowspan: ({ row }: { row: TableItem }) => {
              const rowSpan = tableData.value.filter((item) => item.immute_domain === row.immute_domain).length;
              return rowSpan > 1 ? rowSpan : 1;
            },
            render: ({ row }: { row: TableItem }) => (
              <>
                {
                  props.options?.is_master ? <bk-tag theme="info">{t('主')}</bk-tag> : <bk-tag theme="success">{t('从')}</bk-tag>
                }
                <span class="ml-4">{row.immute_domain}</span>
              </>
            ),
          },
          {
            label: t('账号'),
            field: 'user',
            width: 240,
            rowspan: ({ row }: { row: TableItem }) => {
              const rowSpan = tableData.value.filter((item) => item.immute_domain === row.immute_domain && item.user === row.user).length;
              return rowSpan > 1 ? rowSpan : 1;
            },
          },
          {
            label: t('匹配中的访问源'),
            field: 'match_ip',
            width: 240,
            rowspan: ({ row }: { row: TableItem }) => {
              const rowSpan = tableData.value.filter((item) => item.immute_domain === row.immute_domain && item.user === row.user && item.match_ip === row.match_ip).length;
              return rowSpan > 1 ? rowSpan : 1;
            },
          },
          {
            label: t('匹配中的 DB'),
            field: 'match_db',
            width: 240,
            render: ({ row }: { row: TableItem }) => <bk-tag>{row.match_db}</bk-tag>
          },
          {
            label: t('权限'),
            field: 'priv',
            width: 240,
            render: ({ row }: { row: TableItem }) => {
              const { priv } = row
              const privList = priv.split(',')

              return privList.map((privItem, index) => (
                <>
                  { index !== 0 && <span>，</span> }
                  <span>{privItem}</span>
                  { isSensitivePriv(props.options?.account_type || AccountTypes.MYSQL, privItem) && (
                    <bk-tag
                      size="small"
                      theme="warning"
                      class="ml-4"
                    >
                      {t('敏感')}
                    </bk-tag>
                  )}
                </>
              ))
            }
          },
        ]
      },
      {
        label: t('查询的对象 IP'),
        children: [
          {
            label: t('源客户端 IP'),
            field: 'ip',
            width: 240,
            rowspan: ({ row }: { row: TableItem }) => {
              const rowSpan = tableData.value.filter((item) => item.ip === row.ip).length;
              return rowSpan > 1 ? rowSpan : 1;
            },
            render: ({ row }: { row: TableItem }) => <span style="font-weight: bolder">{row.ip.join('，')}</span>,
          },
        ]
      }
    ];

    if (props.options?.dbs) {
      domainColumns[1].children.push({
        label: t('访问的 DB'),
        field: 'db',
        width: 240,
        render: ({ row }: { row: TableItem }) => row.db.map(dbItem => <bk-tag>{dbItem}</bk-tag>)
      })
    }

    return domainColumns;
  });

  const tableData = computed(() => {
    const { data } = props;
    if (data && data.results.privs_for_cluster) {
      const privsForCluster = data.results.privs_for_cluster;
      return privsForCluster.reduce<TableItem[]>((acc, ipItem) => {
        ipItem.users.forEach(userItem => {
          userItem.match_ips.forEach(matchIpItem => {
            matchIpItem.match_dbs.forEach(({ ip_dbs: ipDbs, priv, ...rest }) => {
              const ip = [];
              const db = [];
              for (const { ip: ipVal, db: dbVal } of ipDbs) {
                ip.push(ipVal);
                db.push(dbVal);
              }
              acc.push({
                immute_domain: ipItem.immute_domain,
                user: userItem.user,
                match_ip: matchIpItem.match_ip,
                priv: priv.toLocaleLowerCase(),
                ip,
                db,
                ...rest
              });
            });
          });
        });
        return acc;
      }, []);
    }

    return [];
  });

  const handleTableLimitChange = (value: number) => {
    emits('page-limit-change', value)
  }

  const handleTableValueChange = (value: number) => {
    emits('page-value-change', value)
  }
</script>
