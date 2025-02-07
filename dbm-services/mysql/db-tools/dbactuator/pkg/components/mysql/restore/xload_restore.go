package restore

import (
	"fmt"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/mohae/deepcopy"
	"github.com/pkg/errors"

	"dbm-services/common/go-pubpkg/logger"
	"dbm-services/mysql/db-tools/dbactuator/pkg/components"
	"dbm-services/mysql/db-tools/dbactuator/pkg/components/computil"
	"dbm-services/mysql/db-tools/dbactuator/pkg/core/cst"
	"dbm-services/mysql/db-tools/dbactuator/pkg/native"
	"dbm-services/mysql/db-tools/dbactuator/pkg/tools"
	"dbm-services/mysql/db-tools/dbactuator/pkg/util"
	"dbm-services/mysql/db-tools/dbactuator/pkg/util/mysqlutil"
	"dbm-services/mysql/db-tools/dbactuator/pkg/util/osutil"
)

// XLoad TODO
type XLoad struct {
	*RestoreParam

	taskDir   string           // 依赖 BackupInfo.WorkDir ${work_dir}/doDr_${id}/${port}/
	targetDir string           // 备份解压后的目录，${taskDir}/backupBaseName/
	dbWorker  *native.DbWorker // TgtInstance
	myCnf     *util.CnfFile
}

func (x *XLoad) initDirs() error {
	if x.BackupInfo.WorkDir == "" {
		return errors.Errorf("work_dir %s should not be empty", x.WorkDir)
	}
	if x.WorkID == "" {
		x.WorkID = newTimestampString()
	}
	x.taskDir = fmt.Sprintf("%s/doDr_%s/%d", x.WorkDir, x.WorkID, x.TgtInstance.Port)
	if err := osutil.CheckAndMkdir("", x.taskDir); err != nil {
		return err
	}
	/*
		if x.backupBaseName == "" {
			return errors.Errorf("backup file baseName [%s] error", x.backupBaseName)
		}
	*/
	//x.targetDir = fmt.Sprintf("%s/%s", x.taskDir, x.backupBaseName)
	x.targetDir = fmt.Sprintf("%s/%s", x.taskDir, x.BackupInfo.infoObj.GetMetafileBasename())
	return nil
}

// Init TODO
func (x *XLoad) Init() error {
	cnfFileName := util.GetMyCnfFileName(x.TgtInstance.Port)
	cnfFile := &util.CnfFile{FileName: cnfFileName}
	var err error
	if err = cnfFile.Load(); err != nil {
		logger.Info("xload get my.conf failed %v", cnfFileName)
		return errors.WithStack(err)
	} else {
		x.myCnf = cnfFile
		x.TgtInstance.Socket, err = x.myCnf.GetMySQLSocket()
		if err != nil {
			logger.Warn("xload fail to get mysqld socket: %s", cnfFileName)
		}
	}
	if err = x.BackupInfo.infoObj.ValidateFiles(); err != nil {
		return err
	}
	if err = x.initDirs(); err != nil {
		return err
	}
	// logger.Info("tgtInstance: %+v", x.TgtInstance)
	x.dbWorker, err = x.TgtInstance.Conn()
	if err != nil {
		logger.Warn("xload fail to connect mysqld %s", cnfFileName)
	}
	// x.dbWorker.Db.Close()
	logger.Info("XLoad params: %+v", x)
	return nil
}

// PreCheck TODO
func (x *XLoad) PreCheck() error {
	toolset, err := tools.NewToolSetWithPick(tools.ToolXLoad, tools.ToolQPress)
	if err != nil {
		return err
	}
	if err := x.Tools.Merge(toolset); err != nil {
		return err
	}
	// 工具可执行权限

	// 物理恢复要求目标是空闲实例
	return nil
}

// Start TODO
func (x *XLoad) Start() error {
	if err := x.BackupInfo.infoObj.UntarFiles(x.taskDir); err != nil {
		return err
	}
	if err := x.DoXLoad(); err != nil {
		return err
	}
	return nil
}

// WaitDone TODO
func (x *XLoad) WaitDone() error {
	return nil
}

// PostCheck 物理备份肯修改了密码，验证能否用 ADMIN 登录
func (x *XLoad) PostCheck() error {
	_, err := x.TgtInstance.Conn()
	if err != nil {
		return errors.Wrap(err, "目标实例连接失败")
	}
	return nil
}

// ReturnChangeMaster TODO
func (x *XLoad) ReturnChangeMaster() (*mysqlutil.ChangeMaster, error) {
	return x.getChangeMasterPos(x.SrcInstance)
}

// getChangeMasterPos godoc
// xtrabackup 在 master，只有 xtrabackup_binlog_info
// xtrabackup 在 slave, 有 xtrabackup_binlog_info, xtrabackup_slave_info
func (x *XLoad) getChangeMasterPos(masterInst native.Instance) (*mysqlutil.ChangeMaster, error) {
	XtraSlaveInfoFile := filepath.Join(x.targetDir, "xtrabackup_slave_info") // 当前备份的对端 master 位点
	XtraBinlogInfo := filepath.Join(x.targetDir, "xtrabackup_binlog_info")   // 当前备份所在实例位点, 可能master可能slave

	binlogInfo, err := osutil.ReadFileString(XtraBinlogInfo)
	if err != nil {
		return nil, err
	}
	// todo Repeater?
	if x.infoObj.BackupRole == cst.BackupRoleMaster ||
		(x.infoObj.BackupRole == cst.BackupRoleSlave &&
			x.infoObj.BackupHost == masterInst.Host && x.infoObj.BackupPort == masterInst.Port) {
		if cm, err := mysqlutil.ParseXtraBinlogInfo(binlogInfo); err != nil {
			return nil, err
		} else {
			cm.MasterHost = x.infoObj.BackupHost
			cm.MasterPort = x.infoObj.BackupPort
			return cm, nil
		}
	} else if x.infoObj.BackupRole == cst.BackupRoleSlave {
		if slaveInfo, err := osutil.ReadFileString(XtraSlaveInfoFile); err != nil {
			return nil, err
		} else {
			cm := &mysqlutil.ChangeMaster{ChangeSQL: slaveInfo}
			if err := cm.ParseChangeSQL(); err != nil {
				return nil, errors.Wrap(err, slaveInfo)
			}
			return cm, nil
		}
	} else {
		return nil, errors.Errorf("unknown backup_role %s", x.infoObj.BackupRole)
	}
}

// DoXLoad 以下所有步骤必须可重试
func (x *XLoad) DoXLoad() (err error) {
	// 关闭本地mysql
	inst := x.TgtInstance
	param := &computil.ShutdownMySQLParam{MySQLUser: inst.User, MySQLPwd: inst.Pwd,
		Socket: inst.Socket, Host: inst.Host, Port: inst.Port}
	if err := param.ForceShutDownMySQL(); err != nil {
		logger.Error("xload shutdown mysqld failed %s", inst.Socket)
		return err
	}

	// 清理本地目录
	if err = x.cleanXtraEnv(); err != nil {
		return err
	}

	// 调整my.cnf文件
	if err = x.doReplaceCnf(); err != nil {
		return err
	}

	// 恢复物理全备
	if err = x.importData(); err != nil {
		return err
	}

	// 调整目录属主
	if err = x.changeDirOwner(); err != nil {
		return err
	}

	// 启动mysql-修复权限
	startParam := computil.StartMySQLParam{
		MediaDir:        cst.MysqldInstallPath,
		MyCnfName:       x.myCnf.FileName,
		MySQLUser:       native.DBUserAdmin, // 用ADMIN
		MySQLPwd:        inst.Pwd,
		Socket:          inst.Socket,
		SkipGrantTables: true, // 以 skip-grant-tables 启动来修复 ADMIN
	}
	logger.Info("start local mysqld with --skip-grant-tables", x.TgtInstance.Port)
	if _, err = startParam.StartMysqlInstance(); err != nil {
		return errors.WithMessage(err, "xload start mysqld with --skip-grant-table")
	}

	// DMB_JOB_xx admin用户清零
	tmpAdminPassInst := deepcopy.Copy(x.TgtInstance).(native.InsObject)
	tmpAdminPassInst.User = native.DBUserAdmin
	//tmpAdminPassInst.ConnBySocket()
	if x.dbWorker, err = tmpAdminPassInst.Conn(); err != nil {
		return err
	} else {
		defer x.dbWorker.Stop()
	}

	serverVersion, err := x.dbWorker.SelectVersion()
	if err != nil {
		//return errors.Wrapf(err, "get mysql version")
		logger.Warn("get version failed: %s. set it to 5.7.20", err.Error())
		serverVersion = "5.7.20" // fake
	}

	// 物理备份，ADMIN密码与 backup instance(cluster?) 相同，修复成
	// 修复ADMIN用户
	if err = x.RepairUserAdminByLocal(inst.Host, native.DBUserAdmin, inst.Pwd, serverVersion); err != nil {
		return err
	}

	// 修复权限
	if err = x.RepairPrivileges(); err != nil {
		return err
	}

	x.dbWorker.Stop()
	logger.Info("restart local mysqld with normal grant mode", x.TgtInstance.Port)
	// 重启mysql（去掉 skip-grant-tables）
	startParam.SkipGrantTables = false
	startParam.MySQLUser = native.DBUserAdmin
	if _, err = startParam.RestartMysqlInstance(); err != nil {
		return err
	}
	// reconnect use ADMIN and temp_job_user pwd(already repaired)
	if x.dbWorker, err = tmpAdminPassInst.Conn(); err != nil {
		return err
	} else {
		defer x.dbWorker.Stop()
	}
	// try to re-create DBM_JOB_xxx
	if x.TgtInstance.User != native.DBUserAdmin {
		adminPriv := components.MySQLAdminAccount{AdminUser: x.TgtInstance.User, AdminPwd: x.TgtInstance.Pwd}.
			GetAccountPrivs(x.TgtInstance.Host)
		adminInitSqls := adminPriv.GenerateInitSql(serverVersion)
		if _, err = x.dbWorker.ExecMore(adminInitSqls); err != nil {
			logger.Warn("fail to reset user %s", x.TgtInstance.User)
		}
	}
	// 修复MyIsam表
	if err = x.RepairAndTruncateMyIsamTables(); err != nil {
		return err
	}

	return nil
}

func (x *XLoad) cleanXtraEnv() error {
	dirs := []string{
		"datadir",
		"innodb_log_group_home_dir",
		"innodb_data_home_dir",
		"relay-log",
		"log_bin",
		"tmpdir",
	}
	return x.CleanEnv(dirs)
}

// doReplaceCnf godoc
// todo 考虑使用 mycnf-change 模块来修改
func (x *XLoad) doReplaceCnf() error {
	items := []string{
		"innodb_data_file_path",
		"innodb_log_files_in_group",
		"innodb_log_file_size",
		"tokudb_cache_size",
	}
	return x.ReplaceMycnf(items)
}

func (x *XLoad) importData() error {
	reg := regexp.MustCompile(`^\s*(.*)/mysqldata/.*$`)
	datadir, err := x.myCnf.GetMySQLDataHomeDir()
	if err != nil {
		return err
	}
	array := reg.FindStringSubmatch(datadir)
	if len(array) != 2 {
		return fmt.Errorf(
			"get mysqldata dir error,len not 2,is %d,info:(%s)",
			len(array), strings.Join(array, ";"),
		)
	}
	mysqlDataDir := array[1]

	xloadPath, err := x.Tools.Get(tools.ToolXLoad)
	if err != nil {
		return err
	}
	param := XLoadParam{
		Host:         x.TgtInstance.Host,
		MysqlDataDir: mysqlDataDir,
		MyCnfFile:    util.GetMyCnfFileName(x.TgtInstance.Port),
		FilePath:     x.targetDir,
		TaskDir:      x.taskDir,
		Client:       xloadPath,
	}
	if err := XLoadData(param); err != nil {
		return err
	}
	return nil
}

func (x *XLoad) changeDirOwner() error {
	dirs := []string{
		"datadir",
		"innodb_log_group_home_dir",
		"innodb_data_home_dir",
		"relay_log",
		"tmpdir",
		"log_bin",
		"slow_query_log_file",
	}
	return x.ChangeDirOwner(dirs)
}

// DecompressMetaFile decompress .pq file and output same file name without suffix
// ex: /home/mysql/dbbackup/xtrabackup/qpress -do xtrabackup_info.qp > xtrabackup_info
func (x *XLoad) DecompressMetaFile(dir string) error {
	client, err := x.Tools.Get(tools.ToolQPress)
	if err != nil {
		return err
	}
	files := []string{
		"xtrabackup_timestamp_info",
		"backup-my.cnf",
		"xtrabackup_binlog_info",
		"xtrabackup_info",
		"xtrabackup_slave_info",
		"xtrabackup_galera_info",
	}

	for _, file := range files {
		compressedFile := fmt.Sprintf("%s.qp", file)
		if _, err := os.Stat(compressedFile); os.IsNotExist(err) {
			continue
		}
		errFile := fmt.Sprintf("%s.err", compressedFile)
		script := fmt.Sprintf(`%s -do %s/%s`, client, dir, compressedFile)
		cmd := osutil.FileOutputCmd{
			Cmd: exec.Cmd{
				Path: "/bin/bash",
				Args: []string{"/bin/bash", "-c", script},
			},
			StdOutFile: path.Join(dir, file),
			StdErrFile: path.Join(dir, errFile),
		}
		if err := cmd.Run(); err != nil {
			return errors.Wrapf(err, "decompress file %s failed, plz check log:%s", compressedFile, errFile)
		}
	}
	return nil
}
