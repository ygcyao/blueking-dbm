package backupexe

import (
	"bufio"
	"bytes"
	"fmt"
	"os"
	"regexp"
	"strings"
	"time"

	"github.com/pkg/errors"
	"github.com/spf13/cast"

	"dbm-services/common/go-pubpkg/cmutil"
	"dbm-services/mysql/db-tools/mysql-dbbackup/pkg/cst"
	"dbm-services/mysql/db-tools/mysql-dbbackup/pkg/src/dbareport"
	"dbm-services/mysql/db-tools/mysql-dbbackup/pkg/src/logger"
	"dbm-services/mysql/db-tools/mysql-dbbackup/pkg/util"
)

type mydumperMetadata struct {
	DumpStarted  string
	DumpFinished string
	MasterStatus map[string]string
	SlaveStatus  map[string]string
	Tables       map[string]interface{}
}

// parseMysqldumpMetadata 从 mysqldump sql 文件里解析 change master / change slave 命令
// 命令被注释，在文件开头的前几行
func parseMysqldumpMetadata(sqlFilePath string) (*mydumperMetadata, error) {
	logger.Log.Infof("start parseMysqldumpMetadata from %s", sqlFilePath)
	sqlFile, err := os.Open(sqlFilePath)
	if err != nil {
		return nil, err
	}
	defer sqlFile.Close()
	var metadata = &mydumperMetadata{
		MasterStatus: map[string]string{},
		SlaveStatus:  map[string]string{},
		Tables:       map[string]interface{}{},
	}

	var bufScanner *bufio.Scanner
	if strings.HasSuffix(sqlFilePath, cst.ZstdSuffix) {
		cmds := []string{"head", "-c", "4096", sqlFilePath, "|", CmdZstd, "-d", "-c"}
		outBuf, _, err := cmutil.ExecCommandReturnBytes(true, "", cmds[0], cmds[1:]...)

		if len(outBuf) < 100 { // 返回小于这个长度，肯定非法了，重试一遍
			// https://github.com/facebook/zstd/issues/1358 The maximum block size is indeed a hard limit of 128 KB
			zstdMaxBlockSize := cast.ToString(128 * 1024 * 2)
			cmds = []string{"head", "-c", zstdMaxBlockSize, sqlFilePath, "|", CmdZstd, "-d", "-c"}
			outBuf, _, err = cmutil.ExecCommandReturnBytes(true, "", cmds[0], cmds[1:]...)
		}
		if err != nil {
			logger.Log.Warnf("zstd decode first 4096 bytes failed from %s, err:%s", sqlFilePath, err.Error())
		}
		if len(outBuf) < 100 { // 返回小于这个长度，非法报错
			return nil, errors.Errorf("failed to get binlog position from zst file %s", sqlFilePath)
		}
		bufScanner = bufio.NewScanner(bytes.NewBuffer(outBuf))
	} else {
		bufScanner = bufio.NewScanner(sqlFile)
	}

	var l string                                                                   // one line
	reMaster := `CHANGE MASTER TO MASTER_LOG_FILE='([^']+)', MASTER_LOG_POS=(\d+)` // 本机的位点
	//reSlave := `CHANGE SLAVE TO MASTER_LOG_FILE='([^']+)', MASTER_LOG_POS=(\d+)`   // 本机的 远端master 的位点
	reShowMaster := regexp.MustCompile(reMaster)
	//reShowSlave := regexp.MustCompile(reSlave)
	for bufScanner.Scan() {
		l = bufScanner.Text()
		matches := reShowMaster.FindStringSubmatch(l)
		if len(matches) == 3 {
			metadata.MasterStatus["File"] = matches[1]
			metadata.MasterStatus["Position"] = matches[2]
			break
		}
		/*
			matches2 := reShowSlave.FindStringSubmatch(l)
			if len(matches2) == 3 {
				metadata.SlaveStatus["File"] = matches2[1]
				metadata.SlaveStatus["Position"] = matches2[2]
				break
			}
		*/
	}
	return metadata, nil
}

func parseMydumperMetadata(metadataFile string) (*mydumperMetadata, error) {
	logger.Log.Infof("start parseMydumperMetadata %s", metadataFile)
	metafile, err := os.Open(metadataFile)
	if err != nil {
		return nil, err
	}
	defer metafile.Close()

	var metadata = &mydumperMetadata{
		MasterStatus: map[string]string{},
		SlaveStatus:  map[string]string{},
		Tables:       map[string]interface{}{},
	}
	var flagMaster, flagSlave, flagTable bool
	// lines := cmutil.SplitAnyRuneTrim(string(bs), "\n")
	var l string // one line
	buf := bufio.NewScanner(metafile)
	for buf.Scan() {
		l = buf.Text()
		logger.Log.Debugf("metadata line: %s", l)
		if strings.HasPrefix(l, "# Started dump at:") {
			metadata.DumpStarted = strings.Trim(strings.TrimPrefix(l, "# Started dump at:"), "' ")
			continue
		} else if strings.HasPrefix(l, "# Finished dump at:") {
			metadata.DumpFinished = strings.Trim(strings.TrimPrefix(l, "# Finished dump at:"), "' ")
			continue
		} else if strings.HasPrefix(l, "[master]") { // 当在 master 备份时，只有这个，当在 slave 上备份时，这代表的是 slave的位点
			flagMaster = true
			flagSlave = false
			flagTable = false
			continue
		} else if strings.HasPrefix(l, "[replication]") {
			flagSlave = true
			flagMaster = false
			flagTable = false
			continue
		} else if strings.HasPrefix(l, "[`") { // table info
			flagTable = true
			flagMaster = false
			flagSlave = false
			continue
		}
		if strings.Contains(l, "=") {
			// parse master / slave info
			// # Channel_Name = '' # It can be use to setup replication FOR CHANNEL
			kv := strings.SplitN(l, "=", 2)
			key := strings.TrimSpace(strings.TrimLeft(kv[0], "#"))
			valTmp := strings.SplitN(kv[1], "# ", 2)
			val := strings.TrimSpace(strings.Trim(valTmp[0], "' "))
			logger.Log.Debugf("key=%s val=%s", key, val)
			if flagMaster {
				metadata.MasterStatus[key] = val
			} else if flagSlave {
				metadata.SlaveStatus[key] = val
			} else if flagTable {
				// metadata.Tables[key] = val
				continue
			}
		} else {
			continue
		}
	}
	return metadata, nil
}

// openXtrabackupFile parse xtrabackup_info
// 因为文件不大，直接 readall
func openXtrabackupFile(binpath string, fileName string, tmpFileName string) (*bytes.Buffer, error) {
	if exist, _ := util.FileExist(fileName); exist {
		util.CopyFile(tmpFileName, fileName)
	} else if exist, _ := util.FileExist(fileName + ".qp"); exist {
		qpressStr := fmt.Sprintf(`%s -do %s > %s`, binpath, fileName+".qp", tmpFileName)
		if err := util.ExeCommand(qpressStr); err != nil {
			return nil, err
		}
	} else {
		err := fmt.Errorf("%s dosen't exist", fileName)
		return nil, err
	}
	content, err := os.ReadFile(tmpFileName)
	//tmpFile, err := os.Open(tmpFileName)
	if err != nil {
		return nil, err
	}

	return bytes.NewBuffer(content), nil
}

// parseXtraInfo get start_time / end_time / binlog pos from xtrabackup_info
// return startTime,endTime,error
/*
uuid = xx-4347-11ef-8de0-xxxxxxxxx
name =
tool_name = xtrabackup_57
tool_command = --defaults-file=/etc/my.cnf.3306 --host=x.x.x.x --port=3306 --user=xx --password=...
tool_version = 2.4.11
ibbackup_version = 2.4.11
server_version = 5.7.20-tmysql-3.3-log
start_time = 2024-07-16 15:44:13
end_time = 2024-07-16 15:44:20
lock_time = 0
binlog_pos = filename 'binlog20000.000353', position '181942'
innodb_from_lsn = 0
innodb_to_lsn = 980247078
partial = N
incremental = N
format = file
compact = N
compressed = compressed
encrypted = N
*/
func parseXtraInfo(qpress string, fileName string, tmpFileName string, metaInfo *dbareport.IndexContent) error {
	fileBytes, err := openXtrabackupFile(qpress, fileName, tmpFileName)
	if err != nil {
		return err
	}
	scanner := bufio.NewScanner(fileBytes)
	var startTimeStr, endTimeStr string
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "start_time = ") { // start_time = 2024-07-16 15:44:13
			startTimeStr = strings.TrimPrefix(line, "start_time = ")
			metaInfo.BackupBeginTime, err = time.ParseInLocation(cst.XtrabackupTimeLayout, startTimeStr, time.Local)
			if err != nil {
				return errors.Wrapf(err, "parse BackupBeginTime %s", startTimeStr)
			}
		}
		if strings.HasPrefix(line, "end_time = ") { // end_time = 2024-07-16 15:44:20
			endTimeStr = strings.TrimPrefix(line, "end_time = ")
			metaInfo.BackupEndTime, err = time.ParseInLocation(cst.XtrabackupTimeLayout, endTimeStr, time.Local)
			if err != nil {
				return errors.Wrapf(err, "parse BackupEndTime %s", endTimeStr)
			}
		}
		if strings.HasPrefix(line, "binlog_pos =") { // binlog_pos = filename 'binlog20000.000353', position '181942'
			regBinlogPos := regexp.MustCompile(`.* filename '(.+\.\d+)', position '(\d+)'`)
			if matches := regBinlogPos.FindStringSubmatch(line); len(matches) == 3 {
				metaInfo.BinlogInfo.ShowMasterStatus = &dbareport.StatusInfo{
					BinlogFile: matches[1],
					BinlogPos:  matches[2],
				}
			}
		}
	}
	return nil
}

// parseXtraTimestamp get consistentTime from xtrabackup_timestamp_info(if exists)
/*
20240716_154420
*/
func parseXtraTimestamp(qpress string, fileName string, tmpFileName string, metaInfo *dbareport.IndexContent) error {
	fileBytes, err := openXtrabackupFile(qpress, fileName, tmpFileName)

	if err != nil {
		return err
	} else {
		scanner := bufio.NewScanner(fileBytes)
		for scanner.Scan() {
			line := scanner.Text()
			metaInfo.BackupConsistentTime, err = time.ParseInLocation("20060102_150405", line, time.Local)
			if err != nil {
				return errors.Wrapf(err, "parse BackupConsistentTime %s", line)
			}
		}
	}
	return nil
}

// parseXtraBinlogInfo parse xtrabackup_binlog_info / xtrabackup_binlog_pos_innodb to get master info
/*
binlog20000.000353      181942
*/
func parseXtraBinlogInfo(qpress string, fileName string, tmpFileName string) (*dbareport.StatusInfo, error) {
	fileBytes, err := openXtrabackupFile(qpress, fileName, tmpFileName)
	if err != nil {
		return nil, err
	}
	showMasterStatus := &dbareport.StatusInfo{
		//MasterHost: backupResult.MysqlHost, // use backup_host as local binlog file_pos host
		//MasterPort: backupResult.MysqlPort,
	}
	// 预期应该只有一条记录
	fileContentStr := strings.ReplaceAll(fileBytes.String(), ",\n", ",")
	words := strings.Fields(fileContentStr)
	if len(words) < 2 {
		return nil, errors.Errorf("failed to parse xtrabackup_binlog_info, get %s", fileContentStr)
	}
	showMasterStatus.BinlogFile = words[0]
	showMasterStatus.BinlogPos = words[1]
	if len(words) >= 3 {
		showMasterStatus.Gtid = words[2]
	}
	return showMasterStatus, nil
}

// parseXtraSlaveInfo parse xtrabackup_slave_info to get slave info
/*
CHANGE MASTER TO MASTER_LOG_FILE='binlog20000.009159', MASTER_LOG_POS=6488;
*/
func parseXtraSlaveInfo(qpress string, fileName string, tmpFileName string) (*dbareport.StatusInfo, error) {
	fileBytes, err := openXtrabackupFile(qpress, fileName, tmpFileName)
	if err != nil {
		return nil, err
	}

	showSlaveStatus := &dbareport.StatusInfo{
		//MasterHost: backupResult.MasterHost,
		//MasterPort: backupResult.MysqlPort,
	}
	scanner := bufio.NewScanner(fileBytes)
	for scanner.Scan() {
		line := scanner.Text()
		re := regexp.MustCompile(`MASTER_LOG_FILE='(\S+)',\s+MASTER_LOG_POS=(\d+)`)
		matches := re.FindStringSubmatch(line)
		if len(matches) == 3 {
			showSlaveStatus.BinlogFile = matches[1]
			showSlaveStatus.BinlogPos = matches[2]
		}
	}
	logger.Log.Warnf("parseXtraSlaveInfo=%+v", showSlaveStatus)
	return showSlaveStatus, nil
}
