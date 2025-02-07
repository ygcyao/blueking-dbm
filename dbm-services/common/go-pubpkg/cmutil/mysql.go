// Package cmutil TODO
package cmutil

import (
	"regexp"
	"strconv"
	"strings"

	"github.com/pkg/errors"
)

// GetMysqlSystemDatabases TODO
func GetMysqlSystemDatabases(version string) []string {
	DBs := []string{"information_schema", "mysql", "performance_schema"}

	if MySQLVersionParse(version) > MySQLVersionParse("5.7.0") {
		DBs = append(DBs, "sys")
	} else if MySQLVersionParse(version) < MySQLVersionParse("5.0.0") {
		DBs = []string{"mysql"}
	} else if MySQLVersionParse(version) < MySQLVersionParse("5.5.0") {
		DBs = []string{"information_schema", "mysql"}
	}
	return DBs
}

// GetGcsSystemDatabases 获取mysql系统库列表，包括GCS监控管理库
// 小于5.0："mysql", "db_infobase", "test"
// 小于5.5："information_schema", "mysql", "db_infobase", "test"
// 小于5.7："information_schema", "mysql", "performance_schema", "db_infobase", "test"
// 大于5.7："information_schema", "mysql", "performance_schema", "sys","db_infobase", "test"
func GetGcsSystemDatabases(version string) []string {
	DBs := GetMysqlSystemDatabases(version)
	DBs = append(DBs, "db_infobase")
	DBs = append(DBs, "test")
	return DBs
}

// GetGcsSystemDatabasesIgnoreTest TODO
func GetGcsSystemDatabasesIgnoreTest(version string) []string {
	DBs := GetMysqlSystemDatabases(version)
	DBs = append(DBs, "db_infobase")
	return DBs
}

// TmysqlVersionParse TODO
/*
input: select version() 获取到的string
output: 获取tmysql带的版本号
example:
5.7.20-tmysql-3.1.5-log ==> 3*1000000 + 1*1000 + 5 ==> 3001005
返回0，表示非tmysql
*/
func TmysqlVersionParse(version string) uint64 {
	re := regexp.MustCompile(`tmysql-([\d]+).?([\d]+)?.?([\d]+)?`)
	return mysqlVersionParse(re, version)
}

// MySQLVersionParse ():
// input: select version() 获取到的string
// output: 获取tmysql中的mysql前缀版本
// example:
// 5.7.20-tmysql-3.1.5-log ==> 5*1000000 + 7*1000 + 20 ==> 5007020
// MySQL5.1.13 ==>  5*1000000+1*1000+13 ==> 5001013
func MySQLVersionParse(version string) uint64 {
	re := regexp.MustCompile(`([\d]+).?([\d]+)?.?([\d]+)?`)
	return mysqlVersionParse(re, version)
}

// SpiderVersionParse 解析spider version
// example:
// mariadb-10.3.7-linux-x86_64-tspider-3.7.6-gcs.tar.gz
// parse version is:3007006
func SpiderVersionParse(version string) uint64 {
	re := regexp.MustCompile(`tspider-([\d]+).?([\d]+)?.?([\d]+)?`)
	return mysqlVersionParse(re, version)
}

func mysqlVersionParse(re *regexp.Regexp, mysqlVersion string) uint64 {
	result := re.FindStringSubmatch(mysqlVersion)
	var (
		total    uint64
		billion  string
		thousand string
		single   string
		// 2.1.5  => 2 * 1000000 + 1 * 1000 + 5
	)
	switch len(result) {
	case 0:
		return 0
	case 4:
		billion = result[1]
		thousand = result[2]
		single = result[3]
		if billion != "" {
			b, err := strconv.ParseUint(billion, 10, 64)
			if err != nil {
				// log.Printf("%s", err)
				b = 0
			}
			total += b * 1000000
		}
		if thousand != "" {
			t, err := strconv.ParseUint(thousand, 10, 64)
			if err != nil {
				// log.Printf("%s", err)
				t = 0
			}
			total += t * 1000
		}
		if single != "" {
			s, err := strconv.ParseUint(single, 10, 64)
			if err != nil {
				s = 0
			}
			total += s
		}
	default:
		return 0
	}
	return total
}

var (
	userPasswordRegex  = regexp.MustCompile(`\s-u\w+.*\s-p(\w+).*`)
	mysqlPasswordRegex = regexp.MustCompile(`\s-p[^\s]+`)
)

// RemovePassword replace password in -u -p pattern
// input:  abcd -uADMIN-pabcd -h127.0.0.1 -P20000 <qq.sql
// output: abcd -uADMIN -pxxxx -h127.0.0.1 -P20000 <qq.sql
func RemovePassword(input string) string {
	return userPasswordRegex.ReplaceAllStringFunc(input, func(sub string) string {
		return mysqlPasswordRegex.ReplaceAllString(sub, " -pxxxx")
	})
}

// GetDbTableName get dbName, tableName from db1.table1 / `db1`.`table1`
func GetDbTableName(dbTableName string) (dbName string, tableName string, err error) {
	ss := strings.SplitN(dbTableName, ".", 2)
	if len(ss) == 2 {
		dbName = strings.Trim(ss[0], "`")
		tableName = strings.Trim(ss[1], "`")
	} else {
		return "", "", errors.Errorf("failed get db table name spliting with . for %s", dbTableName)
	}
	if dbName == "" || tableName == "" {
		return "", "", errors.Errorf("db table cannot be empty parsing %s", dbTableName)
	}
	return
}
