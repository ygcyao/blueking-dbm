package atomredis

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"dbm-services/redis/db-tools/dbactuator/models/myredis"
	"dbm-services/redis/db-tools/dbactuator/models/mysqlite"
	"dbm-services/redis/db-tools/dbactuator/mylog"
	"dbm-services/redis/db-tools/dbactuator/pkg/backupsys"
	"dbm-services/redis/db-tools/dbactuator/pkg/consts"
	"dbm-services/redis/db-tools/dbactuator/pkg/jobruntime"
	"dbm-services/redis/db-tools/dbactuator/pkg/report"
	"dbm-services/redis/db-tools/dbactuator/pkg/util"

	"github.com/go-playground/validator/v10"
	"github.com/gofrs/flock"
	"gopkg.in/yaml.v2"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

// TendisSSDSetLogCount tendisSSD设置log参数
type TendisSSDSetLogCount struct {
	LogCount          int64 `json:"log-count"`
	LogKeepCount      int64 `json:"log-keep-count"`
	SlaveLogKeepCount int64 `json:"slave-log-keep-count"`
}

// RedisBackupParams 备份参数
type RedisBackupParams struct {
	BkBizID                  string               `json:"bk_biz_id" validate:"required"`
	BkCloudID                int64                `json:"bk_cloud_id"`
	Domain                   string               `json:"domain"`
	IP                       string               `json:"ip" validate:"required"`
	Ports                    []int                `json:"ports"`      // 如果端口不连续,可直接指定端口
	StartPort                int                  `json:"start_port"` // 如果端口连续,则可直接指定起始端口和实例个数
	InstNum                  int                  `json:"inst_num"`
	BackupType               string               `json:"backup_type" validate:"required"`
	WithoutToBackupSys       bool                 `json:"without_to_backup_sys"` // 结果不传输到备份系统,默认需传到备份系统
	SSDLogCount              TendisSSDSetLogCount `json:"ssd_log_count"`         // 该参数在tendissd 重做dr时,备份master需设置
	BackupClientStrorageType string               `json:"backup_client_storage_type"`
}

// RedisBackup backup atomjob
type RedisBackup struct {
	runtime      *jobruntime.JobGenericRuntime
	params       RedisBackupParams
	Reporter     report.Reporter `json:"-"`
	backupClient backupsys.BackupClient
	sqdb         *gorm.DB
}

// 无实际作用,仅确保实现了 jobruntime.JobRunner 接口
var _ jobruntime.JobRunner = (*RedisBackup)(nil)

// NewRedisBackup new
func NewRedisBackup() jobruntime.JobRunner {
	return &RedisBackup{}
}

// Init 初始化
func (job *RedisBackup) Init(m *jobruntime.JobGenericRuntime) error {
	job.runtime = m
	err := json.Unmarshal([]byte(job.runtime.PayloadDecoded), &job.params)
	if err != nil {
		job.runtime.Logger.Error(fmt.Sprintf("json.Unmarshal failed,err:%+v", err))
		return err
	}
	// 参数有效性检查
	validate := validator.New()
	err = validate.Struct(job.params)
	if err != nil {
		if _, ok := err.(*validator.InvalidValidationError); ok {
			job.runtime.Logger.Error("RedisBackup Init params validate failed,err:%v,params:%+v",
				err, job.params)
			return err
		}
		for _, err := range err.(validator.ValidationErrors) {
			job.runtime.Logger.Error("RedisBackup Init params validate failed,err:%v,params:%+v",
				err, job.params)
			return err
		}
	}
	// ports 和 inst_num 不能同时为空
	if len(job.params.Ports) == 0 && job.params.InstNum == 0 {
		err = fmt.Errorf("RedisBackup ports(%+v) and inst_num(%d) is invalid", job.params.Ports, job.params.InstNum)
		job.runtime.Logger.Error(err.Error())
		return err
	}
	if job.params.InstNum > 0 {
		ports := make([]int, 0, job.params.InstNum)
		for idx := 0; idx < job.params.InstNum; idx++ {
			ports = append(ports, job.params.StartPort+idx)
		}
		job.params.Ports = ports
	}
	if job.params.BackupType != consts.NormalBackupType &&
		job.params.BackupType != consts.ForeverBackupType {
		err = fmt.Errorf("RedisBackup backup_type(%s) not [%s,%s]",
			job.params.BackupType,
			consts.NormalBackupType,
			consts.ForeverBackupType)
		job.runtime.Logger.Error(err.Error())
		return err
	}
	return nil
}

// Name 原子任务名
func (job *RedisBackup) Name() string {
	return "redis_backup"
}

// Run 执行
func (job *RedisBackup) Run() (err error) {
	err = myredis.LocalRedisConnectTest(job.params.IP, job.params.Ports, "")
	if err != nil {
		return
	}
	job.runtime.Logger.Info("all redis instances connect success,server:%s,ports:%s",
		job.params.IP, myredis.ConvertSlotToStr(job.params.Ports))
	var password string
	bakDir := filepath.Join(consts.GetRedisBackupDir(), "dbbak")
	util.MkDirsIfNotExists([]string{bakDir})
	util.LocalDirChownMysql(bakDir)
	err = job.GetReporter()
	if err != nil {
		return
	}
	defer job.Reporter.Close()

	err = job.getSqlDB()
	if err != nil {
		return
	}
	defer job.closeDB()

	err = job.GetBackupClient()
	if err != nil {
		return
	}
	toBackSys := "yes"
	if job.params.WithoutToBackupSys {
		toBackSys = "no"
	}
	bakTasks := make([]*BackupTask, 0, len(job.params.Ports))
	for _, port := range job.params.Ports {
		password, err = myredis.GetRedisPasswdFromConfFile(port)
		if err != nil {
			return
		}
		task := NewFullBackupTask(job.params.BkBizID, job.params.BkCloudID,
			job.params.Domain, job.params.IP, port, password,
			toBackSys, job.params.BackupType, bakDir,
			true, consts.BackupTarSplitSize, job.params.SSDLogCount,
			job.Reporter, job.backupClient, job.sqdb)

		bakTasks = append(bakTasks, task)
	}
	// 串行触发备份和上传备份系统任务
	var bakTaskIDs []string
	for _, task := range bakTasks {
		bakTask := task
		bakTask.GoFullBakcup()
		if bakTask.Err != nil {
			return bakTask.Err
		}
		bakTaskIDs = append(bakTaskIDs, bakTask.BackupTaskID)
	}

	// 上下文输出内容
	job.runtime.PipeContextData = bakTasks

	// 如果是永久备份，那么需要检查上传结果情况
	// 结束时间依赖上传时间最长的那个，所以没必要去并发探测
	if job.params.BackupType == consts.ForeverBackupType {
		job.runtime.Logger.Info(fmt.Sprintf("backup type is[%s], check upload status, task ids [%+v]",
			job.params.BackupType, bakTaskIDs))
		for _, taskId := range bakTaskIDs {
			// 半个小时还没上传成功则认为失败了
			for i := 0; i < 60; i++ {
				// taskStatus>4,上传失败;
				// taskStatus==4,上传成功;
				// taskStatus<4,上传中;
				taskStatus, statusMsg, err := job.backupClient.TaskStatus(taskId)
				// 查询接口失败
				if err != nil {
					job.runtime.Logger.Error(fmt.Sprintf("taskid(%+v) upload error, err:%+v", taskId, err))
					break
				}
				if taskStatus > 4 {
					job.runtime.Logger.Error(fmt.Sprintf("上传失败,statusCode:%d,err:%s", taskStatus, statusMsg))
					break
				} else if taskStatus < 4 {
					job.runtime.Logger.Info(fmt.Sprintf("taskid(%+v)上传中.... statusCode:%d", taskId, taskStatus))
					// 每30s去探测一次
					time.Sleep(30 * time.Second)
					continue
				} else if taskStatus == 4 {
					job.runtime.Logger.Info(fmt.Sprintf("taskid(%+v)上传成功", taskId))
					break
				}
			}
		}
	}

	return nil
}

// Retry times
func (job *RedisBackup) Retry() uint {
	return 2
}

// Rollback rollback
func (job *RedisBackup) Rollback() error {
	return nil
}

// GetReporter 上报者
func (job *RedisBackup) GetReporter() (err error) {
	err = report.CreateReportDir()
	if err != nil {
		return
	}
	util.MkDirsIfNotExists([]string{consts.RedisReportSaveDir})
	reportFile := fmt.Sprintf(consts.RedisFullbackupRepoter, time.Now().Local().Format(consts.FilenameDayLayout))
	job.Reporter, err = report.NewFileReport(filepath.Join(consts.RedisReportSaveDir, reportFile))
	util.LocalDirChownMysql(consts.RedisReportSaveDir)
	return
}

func (job *RedisBackup) getSqlDB() (err error) {
	job.sqdb, err = mysqlite.GetLocalSqDB()
	if err != nil {
		return
	}
	err = job.sqdb.AutoMigrate(&RedisFullbackupHistorySchema{})
	if err != nil {
		err = fmt.Errorf("RedisFullbackupHistorySchema AutoMigrate fail,err:%v", err)
		mylog.Logger.Info(err.Error())
		return
	}
	return
}

func (job *RedisBackup) closeDB() {
	mysqlite.CloseDB(job.sqdb)
}

// GetBackupClient 获取备份系统client
func (job *RedisBackup) GetBackupClient() (err error) {
	bkTag := consts.RedisFullBackupTAG
	if job.params.BackupType == consts.ForeverBackupType {
		bkTag = consts.RedisForeverBackupTAG
	}
	// job.backupClient = backupsys.NewIBSBackupClient(consts.IBSBackupClient, bkTag)
	job.backupClient, err = backupsys.NewCosBackupClient(consts.COSBackupClient, consts.COSInfoFile,
		bkTag, job.params.BackupClientStrorageType)
	if err != nil && strings.HasPrefix(err.Error(), "backup_client path not found") {
		// 如果 backup_client 不存在,先忽略错误
		return nil
	}
	return
}

// RedisFullbackupHistorySchema TODO
type RedisFullbackupHistorySchema struct {
	ID         int64  `json:"-" gorm:"primaryKey;column:id;not null`
	ReportType string `json:"report_type" gorm:"column:report_type;not null;default:''"`
	BkBizID    string `json:"bk_biz_id"  gorm:"column:bk_biz_id;not null;default:''"`
	BkCloudID  int64  `json:"bk_cloud_id" gorm:"column:bk_cloud_id;not null;default:0"`
	ServerIP   string `json:"server_ip" gorm:"column:server_ip;not null;default:''"`
	ServerPort int    `json:"server_port" gorm:"column:server_port;not null;default:0"`
	Domain     string `json:"domain" gorm:"column:domain;not null;default:'';index"`
	// RedisInstance or TendisplusInstance or TendisSSDInstance
	DbType    string `json:"db_type" gorm:"column:db_type;not null;default:''"`
	Role      string `json:"role" gorm:"column:role;not null;default:''"`
	BackupDir string `json:"backup_dir" gorm:"column:backup_dir;not null;default:''"`
	// 备份的目标文件
	BackupFile string `json:"backup_file" gorm:"column:backup_file;not null;default:''"`
	// 备份文件大小(已切割 or 已压缩 or 已打包)
	BackupFileSize int64  `json:"backup_file_size" gorm:"column:backup_file_size;not null;default:0"`
	BackupTaskID   string `json:"backup_taskid" gorm:"column:backup_taskid;not null;default:''"`
	// 目前为空
	BackupMD5 string `json:"backup_md5" gorm:"column:backup_md5;not null;default:''"`
	// REDIS_FULL
	BackupTag string `json:"backup_tag" gorm:"column:backup_tag;not null;default:''"`
	// shard值
	ShardValue string `json:"shard_value" gorm:"column:shard_value;not null;default:''"`
	// 生成全备的起始时间
	StartTime time.Time `json:"start_time" gorm:"column:start_time;not null;default:'';index"`
	// 生成全备的结束时间
	EndTime  time.Time `json:"end_time" gorm:"column:end_time;not null;default:'';index"`
	TimeZone string    `json:"time_zone" gorm:"column:time_zone;not null;default:''"`
	Status   string    `json:"status" gorm:"column:status;not null;default:''"`
	Message  string    `json:"message" gorm:"column:message;not null;default:''"`
	// 本地文件是否已删除,未被删除为0,已被删除为1
	LocalFileRemoved int `json:"-" gorm:"column:local_file_removed;not null;default:0"`
}

// TableName TODO
func (r *RedisFullbackupHistorySchema) TableName() string {
	return "redis_fullbackup_history"
}

type redisFullBackupReport struct {
	RedisFullbackupHistorySchema
	StartTime string `json:"start_time"`
	EndTime   string `json:"end_time"`
}

// BackupRecordReport 备份记录上报
func (r *RedisFullbackupHistorySchema) BackupRecordReport(reporter report.Reporter) {
	if reporter == nil {
		return
	}
	reportRow := redisFullBackupReport{
		RedisFullbackupHistorySchema: *r,
		StartTime:                    r.StartTime.Local().Format(time.RFC3339),
		EndTime:                      r.EndTime.Local().Format(time.RFC3339),
	}
	tmpBytes, _ := json.Marshal(reportRow)
	reporter.AddRecord(string(tmpBytes)+"\n", true)
}

// BackupTask redis备份task
type BackupTask struct {
	RedisFullbackupHistorySchema
	Password         string               `json:"-"`
	ToBackupSystem   string               `json:"-"`
	BackupType       string               `json:"-"` // 常规备份、下线备份
	DataSize         uint64               `json:"-"` // redis实例数据大小
	DataDir          string               `json:"-"`
	TarSplit         bool                 `json:"-"` // 是否对tar文件做split
	TarSplitPartSize string               `json:"-"`
	Cli              *myredis.RedisClient `json:"-"`
	SSDLogCount      TendisSSDSetLogCount `json:"-"`
	reporter         report.Reporter
	backupClient     backupsys.BackupClient
	sqdb             *gorm.DB
	Err              error `json:"-"`
}

// NewFullBackupTask new backup task
func NewFullBackupTask(bkBizID string, bkCloudID int64,
	domain, ip string, port int, password,
	toBackupSys, backupType, backupDir string, tarSplit bool, tarSplitSize string,
	ssdLogCount TendisSSDSetLogCount, reporter report.Reporter,
	bakCli backupsys.BackupClient,
	sqDB *gorm.DB) *BackupTask {
	timeZone, _ := time.Now().Local().Zone()
	backupTag := consts.RedisFullBackupTAG
	if backupType == consts.ForeverBackupType {
		backupTag = consts.RedisForeverBackupTAG
	}
	ret := &BackupTask{
		Password:         password,
		ToBackupSystem:   toBackupSys,
		BackupType:       backupType,
		TarSplit:         tarSplit,
		TarSplitPartSize: tarSplitSize,
		SSDLogCount:      ssdLogCount,
		reporter:         reporter,
		backupClient:     bakCli,
		sqdb:             sqDB,
	}
	ret.RedisFullbackupHistorySchema = RedisFullbackupHistorySchema{
		ReportType:   consts.RedisFullBackupReportType,
		BkBizID:      bkBizID,
		BkCloudID:    bkCloudID,
		Domain:       domain,
		ServerIP:     ip,
		ServerPort:   port,
		BackupDir:    backupDir,
		BackupTaskID: "",
		BackupMD5:    "",
		BackupTag:    backupTag,
		TimeZone:     timeZone,
	}
	return ret
}

// Addr string
func (task *BackupTask) Addr() string {
	return task.ServerIP + ":" + strconv.Itoa(task.ServerPort)
}

// ToString ..
func (task *BackupTask) ToString() string {
	tmpBytes, _ := json.Marshal(task)
	return string(tmpBytes)
}

// GoFullBakcup 执行备份task,本地备份+上传备份系统
func (task *BackupTask) GoFullBakcup() {
	mylog.Logger.Info("redis(%s) begin to backup", task.Addr())
	defer func() {
		if task.Err != nil {
			mylog.Logger.Error("redis(%s) backup fail", task.Addr())
		} else {
			mylog.Logger.Info("redis(%s) backup success", task.Addr())
		}
	}()

	var locked bool
	task.newConnect()
	if task.Err != nil {
		return
	}
	defer task.Cli.Close()
	mylog.Logger.Info("redis(%s) connect success", task.Addr())

	// 获取文件锁
	lockFile := fmt.Sprintf("lock.%s.%d", task.ServerIP, task.ServerPort)
	lockFile = filepath.Join(task.BackupDir, "backup", lockFile)
	util.MkDirsIfNotExists([]string{filepath.Dir(lockFile)})
	util.LocalDirChownMysql(filepath.Dir(lockFile))
	mylog.Logger.Info(fmt.Sprintf("redis(%s) try to get filelock:%s", task.Addr(), lockFile))

	// 每10秒检测一次是否上锁成功,最多等待3小时
	flock := flock.New(lockFile)
	lockctx, lockcancel := context.WithTimeout(context.Background(), 3*time.Hour)
	defer lockcancel()
	locked, task.Err = flock.TryLockContext(lockctx, 10*time.Second)
	if task.Err != nil {
		task.Err = fmt.Errorf("try to get filelock(%s) fail,err:%v,redis(%s)", lockFile, task.Err, task.Addr())
		mylog.Logger.Error(task.Err.Error())
		return
	}
	if !locked {
		return
	}
	defer flock.Unlock()

	defer func() {
		if task.Err != nil && task.Status == "" {
			task.Message = task.Err.Error()
			task.Status = consts.BackupStatusFailed
		}
		task.BackupRecordReport(task.reporter)
	}()

	task.Status = consts.BackupStatusRunning
	task.Message = "start backup..."
	task.StartTime = time.Now().Local()
	task.EndTime = time.Now().Local()
	task.BackupRecordReport(task.reporter)

	mylog.Logger.Info(fmt.Sprintf("redis(%s) dbType:%s start backup...", task.Addr(), task.DbType))

	task.PrecheckDisk()
	if task.Err != nil {
		return
	}
	task.getRedisShardVal()
	if task.Err != nil {
		return
	}

	// 如果有备份正在执行,则先等待其完成
	task.Err = task.Cli.WaitForBackupFinish()
	if task.Err != nil {
		return
	}
	if task.DbType == consts.TendisTypeRedisInstance {
		task.RedisInstanceBackup()
	} else if task.DbType == consts.TendisTypeTendisplusInsance {
		task.TendisplusInstanceBackup()
	} else if task.DbType == consts.TendisTypeTendisSSDInsance {
		task.TendisSSDSetLougCount()
		if task.Err != nil {
			return
		}
		task.TendisSSDInstanceBackup()
	}
	if task.Err != nil {
		return
	}
	defer task.BackupRecordSaveToLocalDB()
	// 备份上传备份系统
	if strings.ToLower(task.ToBackupSystem) != "yes" {
		task.Status = consts.BackupStatusLocalSuccess
		task.Message = "本地备份成功,无需上传备份系统"
		return
	}
	// backup-client 不存在,无法上传备份系统
	if task.backupClient == nil {
		task.Status = consts.BackupStatusLocalSuccess
		task.Message = "本地备份成功,backup-client不存在,无法上传备份系统"
		return
	}
	task.TransferToBackupSystem()
	if task.Err != nil {
		task.Status = consts.BackupStatusToBakSystemFailed
		task.Message = task.Err.Error()
		return
	}
	task.Status = consts.BackupStatusToBakSystemStart
	task.Message = "上传备份系统中"
}

func (task *BackupTask) newConnect() {
	task.Cli, task.Err = myredis.NewRedisClientWithTimeout(task.Addr(), task.Password, 0, consts.TendisTypeRedisInstance,
		2*time.Hour)
	if task.Err != nil {
		return
	}
	task.Role, task.Err = task.Cli.GetRole()
	if task.Err != nil {
		return
	}
	task.DataDir, task.Err = task.Cli.GetDir()
	if task.Err != nil {
		return
	}
	task.DbType, task.Err = task.Cli.GetTendisType()
	if task.Err != nil {
		return
	}
	mylog.Logger.Info("redis(%s) role:%s,dataDir:%s,dbType:%s", task.Addr(), task.Role, task.DataDir, task.DbType)
	// 获取数据量大小
	if task.DbType == consts.TendisTypeRedisInstance {
		task.DataSize, task.Err = task.Cli.RedisInstanceDataSize()
	} else if task.DbType == consts.TendisTypeTendisplusInsance {
		task.DataSize, task.Err = task.Cli.TendisplusDataSize()
	} else if task.DbType == consts.TendisTypeTendisSSDInsance {
		task.DataSize, task.Err = task.Cli.TendisSSDDataSize()
	}
	if task.Err != nil {
		return
	}
	return
}

// PrecheckDisk 磁盘检查
func (task *BackupTask) PrecheckDisk() {
	// 检查磁盘空间是否足够
	bakDiskUsg, err := util.GetLocalDirDiskUsg(task.BackupDir)
	task.Err = err
	if task.Err != nil {
		mylog.Logger.Error("redis:%s backupDir:%s GetLocalDirDiskUsg fail,err:%v", task.Addr(), task.BackupDir, err)
		return
	}
	dataDiskUsg, err := util.GetLocalDirDiskUsg(task.DataDir)
	task.Err = err
	if task.Err != nil {
		mylog.Logger.Error("redis:%s dataDir:%s GetLocalDirDiskUsg fail,err:%v", task.Addr(), task.DataDir, err)
		return
	}
	// 磁盘空间使用已有85%,则报错
	if bakDiskUsg.UsageRatio > 85 || dataDiskUsg.UsageRatio > 85 {
		task.Err = fmt.Errorf("%s disk Used%d%% > 85%% or %s disk Used(%d%%) >85%%",
			task.BackupDir, bakDiskUsg.UsageRatio,
			task.DataDir, dataDiskUsg.UsageRatio)
		mylog.Logger.Error(task.Err.Error())
		return
	}
	if task.DbType == consts.TendisTypeRedisInstance {
		// redisInstance  rdb or aof 都会使用data磁盘空间,如备份会导致磁盘空间超95%则报错
		if int((task.DataSize+dataDiskUsg.UsedSize)*100/dataDiskUsg.TotalSize) > 95 {
			task.Err = fmt.Errorf("redis(%s) data_size(%dMB) bgsave/bgrewriteaof,disk(%s) space will occupy more than 95%%",
				task.Addr(), task.DataSize/1024/1024, task.DataDir)
			mylog.Logger.Error(task.Err.Error())
			return
		}
	}
	if int((task.DataSize+bakDiskUsg.UsedSize)*100/bakDiskUsg.TotalSize) > 95 {
		// 如果备份会导致磁盘空间超95%
		task.Err = fmt.Errorf("redis(%s) data_size(%dMB) backup disk(%s) space will occupy more than 95%%",
			task.Addr(), task.DataSize/1024/1024, task.BackupDir)
		mylog.Logger.Error(task.Err.Error())
		return
	}
	mylog.Logger.Info(fmt.Sprintf(
		"check disk space ok,redis(%s) data_size(%dMB),backupDir disk(%s) available space %dMB",
		task.Addr(), task.DataSize/1024/1024, task.BackupDir, bakDiskUsg.AvailSize/1024/1024))
}

func (task *BackupTask) getRedisShardVal() {
	var enabled bool
	var masterNode *myredis.ClusterNodeData
	enabled, task.Err = task.Cli.IsClusterEnabled()
	if task.Err != nil {
		return
	}
	if enabled {
		masterNode, task.Err = task.Cli.RedisClusterGetMasterNode(task.Addr())
		if task.Err != nil {
			return
		}
		task.ShardValue = masterNode.SlotSrcStr
		return
	}
	if util.FileExists(consts.BkDbmonConfFile) {
		confData, err := os.ReadFile(consts.BkDbmonConfFile)
		if err != nil {
			err = fmt.Errorf("read file(%s) fail,err:%v", consts.BkDbmonConfFile, err)
			mylog.Logger.Warn(err.Error())
			return
		}
		if !strings.Contains(string(confData), "server_shards:") {
			return
		}
		type servers struct {
			Servers []struct {
				ServerShards map[string]string `yaml:"server_shards"`
			} `yaml:"servers"`
		}
		var serversObj servers
		err = yaml.Unmarshal(confData, &serversObj)
		if err != nil {
			err = fmt.Errorf("yaml.Unmarshal fail,err:%v", err)
			mylog.Logger.Warn(err.Error())
			return
		}
		for _, server := range serversObj.Servers {
			for ipPort, shardVal := range server.ServerShards {
				if ipPort == task.Addr() {
					task.ShardValue = shardVal
					return
				}
			}
		}
	}
}

// RedisInstanceBackup redis(cache)实例备份
func (task *BackupTask) RedisInstanceBackup() {
	var srcFile string
	var targetFile string
	var confMap map[string]string
	var fileSize int64
	nowtime := time.Now().Local().Format(consts.FilenameTimeLayout)
	task.StartTime = time.Now().Local()
	if task.Role == consts.RedisMasterRole {
		// redis master backup rdb
		confMap, task.Err = task.Cli.ConfigGet("dbfilename")
		if task.Err != nil {
			return
		}
		rdbFile := confMap["dbfilename"]
		srcFile = filepath.Join(task.DataDir, rdbFile)
		targetFile = filepath.Join(task.BackupDir,
			fmt.Sprintf("%s-redis-%s-%s-%d-%s.rdb",
				task.BkBizID, task.Role, task.ServerIP, task.ServerPort, nowtime))
		task.Err = task.Cli.BgSaveAndWaitForFinish()
	} else {
		srcFile = filepath.Join(task.DataDir, "appendonly.aof")
		targetFile = filepath.Join(task.BackupDir,
			fmt.Sprintf("%s-redis-%s-%s-%d-%s.aof",
				task.BkBizID, task.Role, task.ServerIP, task.ServerPort, nowtime))
		task.Err = task.Cli.BgRewriteAOFAndWaitForDone()
	}
	if task.Err != nil {
		return
	}
	task.EndTime = time.Now().Local()
	cpCmd := fmt.Sprintf("cp %s %s", srcFile, targetFile)
	mylog.Logger.Info(cpCmd)
	_, task.Err = util.RunBashCmd(cpCmd, "", nil, 10*time.Minute)
	if task.Err != nil {
		return
	}
	// aof文件,压缩; redis-server默认会对rdb做压缩,所以rdb文件不做压缩
	if strings.HasSuffix(srcFile, ".aof") {
		targetFile, task.Err = util.CompressFile(targetFile, filepath.Dir(targetFile), true)
		if task.Err != nil {
			return
		}
	}
	task.BackupFile = targetFile
	fileSize, task.Err = util.GetFileSize(targetFile)
	if task.Err != nil {
		mylog.Logger.Error(task.Err.Error())
		return
	}
	task.BackupFileSize = fileSize
	util.LocalFileChmodAllRead(targetFile)
	util.LocalDirChownMysql(task.BackupDir)
	mylog.Logger.Info(fmt.Sprintf("redis(%s) local backup success", task.Addr()))
	return
}

// TendisplusInstanceBackup tendisplus实例备份
func (task *BackupTask) TendisplusInstanceBackup() {
	var tarFile string
	nowtime := time.Now().Local().Format(consts.FilenameTimeLayout)
	backName := fmt.Sprintf("%s-TENDISPLUS-FULL-%s-%s-%d-%s",
		task.BkBizID, task.Role, task.ServerIP, task.ServerPort, nowtime)
	backupFullDir := filepath.Join(task.BackupDir, backName)
	mylog.Logger.Info(fmt.Sprintf("MkdirAll %s", backupFullDir))
	task.Err = util.MkDirsIfNotExists([]string{backupFullDir})
	if task.Err != nil {
		return
	}
	util.LocalDirChownMysql(task.BackupDir)
	task.StartTime = time.Now().Local()
	task.Err = task.Cli.TendisplusBackupAndWaitForDone(backupFullDir)
	if task.Err != nil {
		return
	}
	task.EndTime = time.Now().Local()
	tarFile, task.Err = util.TarADir(backupFullDir, task.BackupDir, true)
	if task.Err != nil {
		mylog.Logger.Error(task.Err.Error())
		return
	}
	task.BackupFile = tarFile
	task.GetBakFilesSize()
	if task.Err != nil {
		return
	}
	util.LocalFileChmodAllRead(task.BackupFile)
	util.LocalDirChownMysql(task.BackupDir)
	mylog.Logger.Info(fmt.Sprintf("tendisplus(%s) local backup success", task.Addr()))
	return
}

// tendisSSDBackupVerify 确定tendissd备份是否是有效的
func (task *BackupTask) tendisSSDBackupVerify(backupFullDir string) {
	var err error
	if !util.FileExists(consts.TredisverifyBin) {
		task.Err = fmt.Errorf("%s not exists", consts.TredisverifyBin)
		mylog.Logger.Error(task.Err.Error())
		return
	}
	cmd := fmt.Sprintf(`
export LD_PRELOAD=/usr/local/redis/bin/deps/libjemalloc.so;
export LD_LIBRARY_PATH=LD_LIBRARY_PATH:/usr/local/redis/bin/deps;
%s %s  1 2>/dev/null
	`, consts.TredisverifyBin, backupFullDir)
	mylog.Logger.Info(cmd)
	_, err = util.RunBashCmd(cmd, "", nil, 1*time.Hour)
	if err != nil {
		task.Err = fmt.Errorf("backupData(%s) verify failed", backupFullDir)
		mylog.Logger.Error(task.Err.Error())
		return
	}
}

// TendisSSDInstanceBackup tendisSSD实例备份
func (task *BackupTask) TendisSSDInstanceBackup() {
	var tarFile string
	var binlogsizeRet myredis.TendisSSDBinlogSize
	nowtime := time.Now().Local().Format(consts.FilenameTimeLayout)
	backName := fmt.Sprintf("%s-TENDISSSD-FULL-%s-%s-%d-%s",
		task.BkBizID, task.Role, task.ServerIP, task.ServerPort, nowtime)
	backupFullDir := filepath.Join(task.BackupDir, backName)
	mylog.Logger.Info(fmt.Sprintf("MkdirAll %s", backupFullDir))
	task.Err = util.MkDirsIfNotExists([]string{backupFullDir})
	if task.Err != nil {
		return
	}
	util.LocalDirChownMysql(task.BackupDir)
	task.StartTime = time.Now().Local()
	binlogsizeRet, _, task.Err = task.Cli.TendisSSDBackupAndWaitForDone(backupFullDir)
	if task.Err != nil {
		return
	}
	task.EndTime = time.Now().Local()

	task.tendisSSDBackupVerify(backupFullDir)
	if task.Err != nil {
		return
	}

	// 备份文件名带上 binlogPos
	fileWithBinlogPos := fmt.Sprintf("%s-%d", backupFullDir, binlogsizeRet.EndSeq)
	task.Err = os.Rename(backupFullDir, fileWithBinlogPos)
	if task.Err != nil {
		task.Err = fmt.Errorf("rename %s to %s fail,err:%v", backupFullDir, fileWithBinlogPos, task.Err)
		mylog.Logger.Error(task.Err.Error())
		return
	}
	backupFullDir = fileWithBinlogPos

	// 只做打包,不做压缩,rocksdb中已经做了压缩
	tarFile, task.Err = util.TarADir(backupFullDir, task.BackupDir, true)
	if task.Err != nil {
		mylog.Logger.Error(task.Err.Error())
		return
	}
	task.BackupFile = tarFile
	task.GetBakFilesSize()
	if task.Err != nil {
		return
	}
	util.LocalFileChmodAllRead(task.BackupFile)
	util.LocalDirChownMysql(task.BackupDir)
	mylog.Logger.Info(fmt.Sprintf("tendisSSD(%s) local backup success", task.Addr()))
	return
}

// GetBakFilesSize 获取备份文件大小
func (task *BackupTask) GetBakFilesSize() {
	var fileSize int64
	fileSize, task.Err = util.GetFileSize(task.BackupFile)
	if task.Err != nil {
		mylog.Logger.Error(task.Err.Error())
		return
	}
	task.BackupFileSize = fileSize
}

// TendisSSDSetLougCount tendisSSD设置log-count参数
func (task *BackupTask) TendisSSDSetLougCount() {
	if task.SSDLogCount.LogCount > 0 {
		_, task.Err = task.Cli.ConfigSet("log-count", strconv.FormatInt(task.SSDLogCount.LogCount, 10))
		if task.Err != nil {
			return
		}
		mylog.Logger.Info(fmt.Sprintf("%s config set log-count %d success", task.Addr(),
			task.SSDLogCount.LogCount))
	} else {
		mylog.Logger.Info(fmt.Sprintf("%s skip config set log-count(%d)...", task.Addr(),
			task.SSDLogCount.LogCount))
	}
	if task.SSDLogCount.LogKeepCount > 0 {
		_, task.Err = task.Cli.ConfigSet("log-keep-count", strconv.FormatInt(task.SSDLogCount.LogKeepCount, 10))
		if task.Err != nil {
			return
		}
		mylog.Logger.Info(fmt.Sprintf("%s config set log-keep-count %d success", task.Addr(),
			task.SSDLogCount.LogKeepCount))
	} else {
		mylog.Logger.Info(fmt.Sprintf("%s skip config set log-keep-count(%d)...", task.Addr(),
			task.SSDLogCount.LogKeepCount))
	}
	if task.SSDLogCount.SlaveLogKeepCount > 0 {
		_, task.Err = task.Cli.ConfigSet("slave-log-keep-count", strconv.FormatInt(task.SSDLogCount.SlaveLogKeepCount, 10))
		if task.Err != nil {
			return
		}
		mylog.Logger.Info(fmt.Sprintf("%s config set slave-log-keep-count %d success", task.Addr(),
			task.SSDLogCount.SlaveLogKeepCount))
	} else {
		mylog.Logger.Info(fmt.Sprintf("%s skip config set slave-log-keep-count(%d)...", task.Addr(),
			task.SSDLogCount.SlaveLogKeepCount))
	}

}

// TransferToBackupSystem 备份文件上传到备份系统
func (task *BackupTask) TransferToBackupSystem() {
	var msg string
	cliFileInfo, err := os.Stat(consts.COSBackupClient)
	if err != nil {
		task.Err = fmt.Errorf("os.stat(%s) failed,err:%v", consts.COSBackupClient, err)
		mylog.Logger.Error(task.Err.Error())
		return
	}
	if !util.IsExecOther(cliFileInfo.Mode().Perm()) {
		task.Err = fmt.Errorf("%s is unable to execute by other", consts.COSBackupClient)
		mylog.Logger.Error(task.Err.Error())
		return
	}
	mylog.Logger.Info(fmt.Sprintf("redis(%s) backupFiles:%+v start upload backupSystem", task.Addr(), task.BackupFile))
	task.BackupTaskID, task.Err = task.backupClient.Upload(task.BackupFile)
	if task.Err != nil {
		return
	}
	msg = fmt.Sprintf("redis(%s) backupFiles%+v taskid(%+v) uploading to backupSystem",
		task.Addr(), task.BackupFile, task.BackupTaskID)
	mylog.Logger.Info(msg)
	return
}

// BackupRecordSaveToLocalDB 备份信息记录到本地sqlite中
func (task *BackupTask) BackupRecordSaveToLocalDB() {
	mylog.Logger.Info(fmt.Sprintf("(%s)备份记录记录到本地sqlite中....", task.Addr()))
	if task.sqdb == nil || task.Err != nil {
		mylog.Logger.Info(fmt.Sprintf("(%s)sqlite为空或者task存在err，跳过本地记录", task.Addr()))
		return
	}
	task.RedisFullbackupHistorySchema.ID = 0 // 重置为0,以便gorm自增
	task.Err = task.sqdb.Clauses(clause.OnConflict{
		UpdateAll: true,
	}).Create(&task.RedisFullbackupHistorySchema).Error
	if task.Err != nil {
		task.Err = fmt.Errorf("BackupRecordSaveToLocalDB sqdb.Create fail,err:%v", task.Err)
		mylog.Logger.Error(task.Err.Error())
		return
	}
}
