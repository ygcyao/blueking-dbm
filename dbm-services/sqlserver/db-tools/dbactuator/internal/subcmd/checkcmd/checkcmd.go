/*
 * TencentBlueKing is pleased to support the open source community by making 蓝鲸智云-DB管理系统(BlueKing-BK-DBM) available.
 * Copyright (C) 2017-2023 THL A29 Limited, a Tencent company. All rights reserved.
 * Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at https://opensource.org/licenses/MIT
 * Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
 * an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
 * specific language governing permissions and limitations under the License.
 */

// Package sqlservercmd TODO
package checkcmd

import (
	"dbm-services/sqlserver/db-tools/dbactuator/internal/subcmd"
	"dbm-services/sqlserver/db-tools/dbactuator/pkg/util/templates"

	"github.com/spf13/cobra"
)

// NewSQLserverCommand check子命令
func CheckCommand() *cobra.Command {
	cmds := &cobra.Command{
		Use:   "check [check operation]",
		Short: "check Operation Command Line Interface",
		RunE:  subcmd.ValidateSubCommand(),
	}
	groups := templates.CommandGroups{
		{
			Message: "check operation sets",
			Commands: []*cobra.Command{
				CheckAbnormalDBCommand(),
				CheckInstProcessCommand(),
				MssqlServiceCommand(),
			},
		},
	}
	groups.Add(cmds)
	return cmds
}
