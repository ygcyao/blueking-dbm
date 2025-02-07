// Package handler TODOG
package handler

import (
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	_ "runtime/debug" // debug TODO
	"time"

	"dbm-services/mysql/db-partition/model"
	"dbm-services/mysql/db-partition/monitor"

	cron_pkg "github.com/robfig/cron/v3"

	"dbm-services/common/go-pubpkg/errno"
	"dbm-services/mysql/db-partition/service"

	"github.com/gin-gonic/gin"
)

// DryRun TODO
func DryRun(r *gin.Context) {
	fmt.Println("do DryRun!")
	var input service.Checker
	if err := r.ShouldBind(&input); err != nil {
		slog.Error("msg", err)
		SendResponse(r, errno.ErrBind, nil)
		return
	}
	sqls, err := input.DryRun()
	SendResponse(r, err, sqls)
	return

}

// GetPartitionsConfig TODO
func GetPartitionsConfig(r *gin.Context) {
	var input service.QueryParititionsInput
	if err := r.ShouldBind(&input); err != nil {
		slog.Error(err.Error())
		SendResponse(r, errno.ErrBind, nil)
		return
	}
	slog.Info(fmt.Sprintf("bk_biz_id: %d, immute_domains: %s", input.BkBizId, input.ImmuteDomains))
	lists, count, err := input.GetPartitionsConfig()
	// ListResponse 返回信息
	type ListResponse struct {
		Count int64       `json:"count"`
		Items interface{} `json:"items"`
	}
	if err != nil {
		slog.Error(err.Error())
		SendResponse(r, err, nil)
		return
	}
	SendResponse(r, err, ListResponse{
		Count: count,
		Items: lists,
	})
	return
}

// GetPartitionLog TODO
func GetPartitionLog(r *gin.Context) {
	var input service.QueryLogInput
	if err := r.ShouldBind(&input); err != nil {
		slog.Error(err.Error())
		SendResponse(r, errno.ErrBind, nil)
		return
	}
	lists, count, err := input.GetPartitionLog()
	// ListResponse 返回信息
	type ListResponse struct {
		Count int64       `json:"count"`
		Items interface{} `json:"items"`
	}
	if err != nil {
		slog.Error(err.Error())
		SendResponse(r, err, nil)
		return
	}
	SendResponse(r, err, ListResponse{
		Count: count,
		Items: lists,
	})
	return
}

// DeletePartitionsConfig TODO
func DeletePartitionsConfig(r *gin.Context) {
	var input service.DeletePartitionConfigByIds
	if err := r.ShouldBind(&input); err != nil {
		err = errno.ErrReadEntity.Add(err.Error())
		slog.Error(err.Error())
		SendResponse(r, err, nil)
		return
	}
	slog.Info(fmt.Sprintf("bk_biz_id: %d, ids: %v", input.BkBizId, input.Ids))
	err := input.DeletePartitionsConfig()
	if err != nil {
		slog.Error(err.Error())
		SendResponse(r, err, nil)
		return
	}
	SendResponse(r, err, "分区配置信息删除成功！")
	return
}

// DeletePartitionsConfigByCluster TODO
func DeletePartitionsConfigByCluster(r *gin.Context) {
	// 集群下架时，通过cluster_id来删除相关分区配置
	var input service.DeletePartitionConfigByClusterIds
	if err := r.ShouldBind(&input); err != nil {
		err = errno.ErrReadEntity.Add(err.Error())
		slog.Error(err.Error())
		SendResponse(r, err, nil)
		return
	}
	slog.Info(fmt.Sprintf("bk_biz_id: %d, cluster_ids: %v", input.BkBizId, input.ClusterIds))
	err, info := input.DeletePartitionsConfigByCluster()

	if err != nil {
		slog.Error(err.Error())
		SendResponse(r, err, nil)
		return
	}
	SendResponse(r, err, info)
	return
}

// CreatePartitionsConfig TODO
func CreatePartitionsConfig(r *gin.Context) {
	var input service.CreatePartitionsInput
	if err := r.ShouldBind(&input); err != nil {
		err = errno.ErrReadEntity.Add(err.Error())
		slog.Error(err.Error())
		SendResponse(r, err, nil)
		return
	}
	slog.Info(fmt.Sprintf("bk_biz_id: %d, db_app_abbr: %d, immute_domain: %s, creator: %s", input.BkBizId, input.DbAppAbbr,
		input.ImmuteDomain,
		input.Creator))
	err, configIDs := input.CreatePartitionsConfig()
	if err != nil {
		slog.Error(err.Error())
		SendResponse(r, errors.New(fmt.Sprintf("添加分区配置失败!%s", err.Error())), nil)
		return
	}
	// 注意这里内部变量需要首字母大写，不然后面json无法访问
	data := struct {
		ConfigIDs []int  `json:"config_ids"`
		Info      string `json:"info"`
	}{configIDs, "分区配置信息创建成功！"}
	SendResponse(r, nil, data)
	return
}

// DisablePartition TODO
func DisablePartition(r *gin.Context) {
	var input service.DisablePartitionInput
	if err := r.ShouldBind(&input); err != nil {
		err = errno.ErrReadEntity.Add(err.Error())
		slog.Error(err.Error())
		SendResponse(r, err, nil)
		return
	}
	slog.Info(fmt.Sprintf("ids: %v, operator: %s", input.Ids, input.Operator))
	err := input.DisablePartitionConfig()
	if err != nil {
		slog.Error(err.Error())
		SendResponse(r, errors.New(fmt.Sprintf("分区禁用失败!%s", err.Error())), nil)
		return
	}
	SendResponse(r, nil, "分区禁用成功！")
	return
}

// DisablePartitionByCluster 用于集群禁用时停止分区，标志为 offlinewithclu
func DisablePartitionByCluster(r *gin.Context) {
	var input service.DisablePartitionInput
	if err := r.ShouldBind(&input); err != nil {
		err = errno.ErrReadEntity.Add(err.Error())
		slog.Error(err.Error())
		SendResponse(r, err, nil)
		return
	}
	slog.Info(fmt.Sprintf("cluster_ids: %v, operator: %s", input.ClusterIds, input.Operator))
	err := input.DisablePartitionConfigByCluster()
	if err != nil {
		slog.Error(err.Error())
		SendResponse(r, errors.New(fmt.Sprintf("分区禁用失败!%s", err.Error())), nil)
		return
	}
	SendResponse(r, nil, "分区禁用成功！")
	return
}

// EnablePartition TODO
func EnablePartition(r *gin.Context) {
	var input service.EnablePartitionInput
	if err := r.ShouldBind(&input); err != nil {
		err = errno.ErrReadEntity.Add(err.Error())
		slog.Error(err.Error())
		SendResponse(r, err, nil)
		return
	}
	slog.Info(fmt.Sprintf("ids: %v, operator: %s", input.Ids, input.Operator))
	err := input.EnablePartitionConfig()
	if err != nil {
		slog.Error(err.Error())
		SendResponse(r, errors.New(fmt.Sprintf("分区启用失败!%s", err.Error())), nil)
		return
	}
	SendResponse(r, nil, "分区启用成功！")
	return
}

// EnablePartitionByCluster 集群启用时启用分区
func EnablePartitionByCluster(r *gin.Context) {
	var input service.EnablePartitionInput
	if err := r.ShouldBind(&input); err != nil {
		err = errno.ErrReadEntity.Add(err.Error())
		slog.Error(err.Error())
		SendResponse(r, err, nil)
		return
	}
	slog.Info(fmt.Sprintf("ids: %v, operator: %s", input.Ids, input.Operator))
	err := input.EnablePartitionByCluster()
	if err != nil {
		slog.Error(err.Error())
		SendResponse(r, errors.New(fmt.Sprintf("分区启用失败!%s", err.Error())), nil)
		return
	}
	SendResponse(r, nil, "分区启用成功！")
	return
}

// UpdatePartitionsConfig TODO
func UpdatePartitionsConfig(r *gin.Context) {
	var input service.CreatePartitionsInput
	if err := r.ShouldBind(&input); err != nil {
		err = errno.ErrReadEntity.Add(err.Error())
		slog.Error(err.Error())
		SendResponse(r, err, nil)
		return
	}
	slog.Info(fmt.Sprintf("bk_biz_id: %d, immute_domain: %s, updator: %s", input.BkBizId, input.ImmuteDomain,
		input.Updator))
	err := input.UpdatePartitionsConfig()
	if err != nil {
		slog.Error(err.Error())
		SendResponse(r, errors.New(fmt.Sprintf("更新分区配置失败!%s", err.Error())), nil)
		return
	}
	SendResponse(r, nil, "更新分区配置信息创建成功！")
	return
}

// CreatePartitionLog 单据callback，信息记录到日志表中
func CreatePartitionLog(r *gin.Context) {
	var input service.CreatePartitionCronLog
	err := r.ShouldBind(&input)
	if err != nil {
		err = errno.ErrReadEntity.Add(err.Error())
		slog.Error(err.Error())
		SendResponse(r, err, nil)
		return
	}
	tx := model.DB.Self.Begin()
	tb := service.MysqlPartitionCronLogTable
	if input.ClusterType == service.Tendbcluster {
		tb = service.SpiderPartitionCronLogTable
	}
	today := time.Now().Format("20060102")
	for _, l := range input.Logs {
		var vdate string
		if l.CronDate == "" {
			vdate = today
		} else {
			vdate = l.CronDate
		}
		log := &service.PartitionCronLog{ConfigId: l.ConfigId, CronDate: vdate,
			Scheduler: l.Scheduler, CheckInfo: l.CheckInfo, Status: l.Status}
		err = tx.Debug().Table(tb).Create(log).Error
		if err != nil {
			tx.Rollback()
			slog.Error("msg", "add cron log failed", err)
			break
		}
	}
	tx.Commit()
	SendResponse(r, err, nil)
	return
}

// MigrateConfig 迁移分区规则
func MigrateConfig(r *gin.Context) {
	var input service.MigratePara
	err := r.ShouldBind(&input)
	if err != nil {
		err = errno.ErrReadEntity.Add(err.Error())
		slog.Error(err.Error())
		SendResponse(r, err, nil)
		return
	}
	mysqlIds, mysqlFail, spiderIds, spiderFail, err := input.MigrateConfig()
	info := "迁移成功"
	if err != nil {
		slog.Error("msg", "迁移失败", err.Error())
		info = "迁移失败"
	}
	data := struct {
		MigratedMysqlIds  []int  `json:"migrated_mysql_ids"`
		MysqlMigrateFail  []int  `json:"mysql_migrate_fail"`
		MigratedSpiderIds []int  `json:"migrated_spider_ids"`
		SpiderMigrateFail []int  `json:"spider_migrate_fail"`
		Info              string `json:"info"`
	}{mysqlIds, mysqlFail, spiderIds,
		spiderFail, info}
	SendResponse(r, err, data)
	return
}

// CronEntries 查询定时任务
func CronEntries(r *gin.Context) {
	var entries []cron_pkg.Entry
	for _, v := range service.CronList {
		entries = append(entries, v.Entries()...)
	}
	slog.Info("msg", "entries", entries)
	SendResponse(r, nil, entries)
	return
}

// CronStop 关闭分区定时任务
func CronStop(r *gin.Context) {
	for _, v := range service.CronList {
		v.Stop()
	}
	SendResponse(r, nil, "关闭分区定时任务成功")
	return
}

// CronStart 开启分区定时任务
func CronStart(r *gin.Context) {
	for _, v := range service.CronList {
		v.Start()
	}
	SendResponse(r, nil, "开启分区定时任务成功")
	return
}

// RunOnce 调度执行一次
func RunOnce(r *gin.Context) {
	var input service.PartitionJob
	err := r.ShouldBind(&input)
	if err != nil {
		err = errno.ErrReadEntity.Add(err.Error())
		slog.Error(err.Error())
		SendResponse(r, err, nil)
		return
	}
	if input.ClusterType == service.Tendbha {
		input.ExecuteTendbhaPartition()
	} else if input.ClusterType == service.Tendbcluster {
		input.ExecuteTendbclusterPartition()
	}
	SendResponse(r, nil, "异步执行，执行结果请看日志")
	return
}

// InitMonitor 初始监控配置
func InitMonitor(r *gin.Context) {
	monitor.InitMonitor()
	SendResponse(r, nil, "初始监控配置")
	return
}

// CheckLog 巡检
func CheckLog(r *gin.Context) {
	type CheckPara struct {
		Days int `json:"days"`
	}
	var input CheckPara
	err := r.ShouldBind(&input)
	if err != nil {
		err = errno.ErrReadEntity.Add(err.Error())
		slog.Error(err.Error())
		SendResponse(r, err, nil)
		return
	}
	mysqlNotRun, mysqlFail, err := service.CheckLog(service.Tendbha, input.Days)
	if err != nil {
		slog.Error("msg", "CheckLog error", err)
		SendResponse(r, err, nil)
		return
	}
	spiderNotRun, spiderFail, err := service.CheckLog(service.Tendbcluster, input.Days)
	if err != nil {
		slog.Error("msg", "CheckLog error", err)
		SendResponse(r, err, nil)
		return
	}
	data := struct {
		MysqlNotRun  []*service.CheckSummary `json:"mysql_not_run"`
		MysqlFail    []*service.CheckSummary `json:"mysql_fail"`
		SpiderNotRun []*service.CheckSummary `json:"spider_not_run"`
		SpiderFail   []*service.CheckSummary `json:"spider_fail"`
	}{mysqlNotRun, mysqlFail, spiderNotRun,
		spiderFail}
	SendResponse(r, err, data)
	return
}

// Response TODO
type Response struct {
	Code    int         `json:"code"`
	Message string      `json:"message"`
	Data    interface{} `json:"data"`
}

// SendResponse TODO
func SendResponse(r *gin.Context, err error, data interface{}) {
	code, message := errno.DecodeErr(err)
	dataErr, ok := data.(error)
	if ok {
		message += dataErr.Error()
	}
	// always return http.StatusOK
	r.JSON(http.StatusOK, Response{
		Code:    code,
		Message: message,
		Data:    data,
	})
}
