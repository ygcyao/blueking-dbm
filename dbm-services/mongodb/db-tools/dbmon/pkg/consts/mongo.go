package consts

import (
	"fmt"
	"os"
	"os/user"
	"path"
	"path/filepath"
	"time"

	"github.com/pkg/errors"
)

// meta role
const (
	MetaRoleShardsvrBackup        = "mongo_backup"
	MetaRoleShardsvrBackupNewName = "backup"
	MetaRoleMongos                = "mongos"
)

// twemproxy monitor event categories
const (
	EventMongoRestart = "mongo_restart"
	EventMongoLogin   = "mongo_login"
)

// MongoBin 相关
const (
	mongoSubDirName = "mg"
	MongoToolKit    = "mongo-toolkit-go_Linux"
)

// GetUsername todo
func GetUsername() string {
	currentUser, err := user.Current()
	if err != nil || currentUser.Username == "" {
		panic(errors.Wrap(err, "user.Current()"))
	}
	return currentUser.Username
}

/*
	目录结构
	 /home/mysql/dbtools
		mg/mongo-toolkit-go_Linux
		mg/mongotools/mongodump...
		mg/mongotools/mongorestore.100
	1. mongo-toolkit-go_Linux 在 /home/mysql/dbtools/mg 下
	2. mongodump, mongorestore 在 mongo-toolkit-go_Linux所在目录的 mongotools 下
*/

// GetDbToolDir 获取dbtool目录，在用户目录 dbtools/mg 下
func GetDbToolDir(username string) string {
	if username == "" {
		username = GetUsername()
	}
	return path.Join("/home/", username, "dbtools", mongoSubDirName)
}

// GetDbTool return /home/mysql/dbtools/mg/$name
func GetDbTool(name string) string {
	return path.Join(GetDbToolDir(""), name)
}

// GetMongoBackupReportPath 获取上报目录 /home/mysql/dbareport/mongo/backup/backup-%Y%m%d.log
func GetMongoBackupReportPath() (string, string, string) {
	return GetMongoReportPath("backup")
}

// GetMongoReportPath 获取上报目录 /home/mysql/dbareport/{dbName}/{reportType}/{reportType}-%Y%m%d.log
func GetMongoReportPath(reportType string) (string, string, string) {
	dirName := path.Join(DbaReportSaveDir, "mongo", reportType)
	today := time.Now().Local().Format("20060102")
	fileName := fmt.Sprintf("%s-%s.log", reportType, today)
	return path.Join(dirName, fileName), dirName, fileName
}

// GetMongoBackupDir 获取环境变量 MONGO_BACKUP_DIR,默认值 /data
// 否则,如果目录 /data/dbbak 存在,返回 /data;
// 否则,如果目录 /data1/dbbak 存在,返回 /data1;
// 否则,返回 /data
func GetMongoBackupDir() string {
	dataDir := os.Getenv("MONGO_BACKUP_DIR")
	if dataDir == "" {
		if fileExists(filepath.Join(DataPath, "dbbak")) {
			// /data/dbbak 存在
			dataDir = DataPath
		} else if fileExists(filepath.Join(Data1Path, "dbbak")) {
			// /data1/dbbak 存在
			dataDir = Data1Path
		} else {
			dataDir = DataPath
		}
	}
	return dataDir
}

// GetMongoDataDir 获得数据所在Dir
func GetMongoDataDir(port string) string {
	dataDir := os.Getenv("MONGO_DATA_DIR")
	for _, dirName := range []string{dataDir, Data1Path, DataPath} {
		if dirName == "" {
			continue
		}
		if fileExists(filepath.Join(dirName, "mongodata", port, "mongo.conf")) {
			dataDir = dirName
			break
		}
	}
	return dataDir
}
