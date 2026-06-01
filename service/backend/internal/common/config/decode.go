package config

import (
	"log/slog"
	"strings"
)

type LogLevel slog.Level

func (lld *LogLevel) Decode(value string) error {
	var loggerLevels = map[string]slog.Level{
		"error": slog.LevelError,
		"warn":  slog.LevelWarn,
		"info":  slog.LevelInfo,
		"debug": slog.LevelDebug,
	}
	*lld = LogLevel(loggerLevels[strings.ToLower(value)])
	return nil
}
