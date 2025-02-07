package cmutil

import (
	"regexp"

	"github.com/spf13/cast"
)

// MySQLError TODO
type MySQLError struct {
	Code     int
	Message  string
	Raw      string
	regexStr *regexp.Regexp
}

var mysqlErrors = map[int]MySQLError{
	1146: {
		Code:     1146,
		Message:  "Table doesn't exists",
		regexStr: regexp.MustCompile(`ERROR 1146 .*: Table '(.+)' doesn't exist`)},
	1049: {
		Code:     1049,
		Message:  "Unknown database",
		regexStr: regexp.MustCompile(`ERROR 1049 .*: Unknown database '(.+)'`)},
	1054: {
		Code:     1054,
		Message:  "Unknown column",
		regexStr: regexp.MustCompile(`ERROR 1054 .*: Unknown column '(.+)' in 'field list'`)},
	1193: {
		Code:     1193,
		Message:  "Unknown system variable",
		regexStr: regexp.MustCompile(`Error 1193 .*: Unknown system variable '(.+)'`),
	},
	2002: {
		Code:     2002,
		Message:  "Connection refused",
		regexStr: regexp.MustCompile(`(.*connection refused.*)|(.*Can't connect to local MySQL server.*)`),
	},
	2003: {
		Code:     2003,
		Message:  "Can't connect to MySQL server",
		regexStr: regexp.MustCompile(`ERROR 2003 .*: Can't connect to MySQL server.*`),
	},
	1062: {
		Code:     1062,
		Message:  "Duplicate entry",
		regexStr: regexp.MustCompile(`(?i)Error 1062.*: Duplicate entry.*`),
	},
	1213: {
		Code:     1213,
		Message:  "Deadlock found when trying to get lock",
		regexStr: regexp.MustCompile(`(?i)Error 1213.*: Deadlock found when trying to get lock.*`),
	},
}
var codeParser = regexp.MustCompile(`(?i)Error (\d+) .*`)

// NewMySQLError 对象化 mysql error, err入参要求非 nil
func NewMySQLError(err error) MySQLError {
	if err == nil {
		return MySQLError{
			Code:    0,
			Message: "ok",
		}
	}
	errStr := err.Error()
	matches := codeParser.FindStringSubmatch(errStr)
	if len(matches) == 2 {
		code := cast.ToInt(matches[1])
		if err, ok := mysqlErrors[code]; ok {
			err.Raw = errStr
			return err
		} else {
			return MySQLError{
				Code:    code,
				Message: "Undocumented",
				Raw:     errStr,
			}
		}
	}
	return MySQLError{
		Code:    1,
		Message: "Unknown",
		Raw:     errStr,
	}
}
