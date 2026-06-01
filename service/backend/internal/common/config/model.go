package config

import (
	"time"

	gf "github.com/gofiber/fiber/v3"
	"github.com/sunkek/samsara-components/fiber"
)

// Config is the full service configuration. NoiR Code's gateway is stateless
// (encode/decode delegate to the imaging sidecar), so there is no database,
// broker or cache here — just the HTTP edge, the imaging backend, and a rate
// limiter.
type Config struct {
	Health Health `envconfig:"HEALTH"`
	Log    Log    `envconfig:"LOG"`

	Fiber     Fiber     `envconfig:"FIBER"`
	Imaging   Imaging   `envconfig:"IMAGING"`
	RateLimit RateLimit `envconfig:"RATE_LIMIT"`
}

// Imaging points the gateway at the Python imaging sidecar that owns the
// encode/decode (OpenCV) pipeline.
type Imaging struct {
	BaseURL string        `envconfig:"BASE_URL" default:"http://imaging:8001"`
	Timeout time.Duration `envconfig:"TIMEOUT" default:"30s"`
}

// RateLimit throttles the public encode/decode endpoints per client IP.
type RateLimit struct {
	Max    int           `envconfig:"MAX" default:"30"`
	Window time.Duration `envconfig:"WINDOW" default:"1m"`
}

type Health struct {
	Port     int           `envconfig:"PORT" default:"3333"`
	Interval time.Duration `envconfig:"INTERVAL" default:"1m"`
}

type Log struct {
	Level  LogLevel `envconfig:"LEVEL" default:"info"`
	Source bool     `envconfig:"SOURCE" default:"false"`
}

type Fiber struct {
	Host             string   `envconfig:"HOST" default:"0.0.0.0"`
	Port             int      `envconfig:"PORT" default:"80"`
	PathPrefix       string   `envconfig:"PATH_PREFIX" default:"/api/v1"`
	BodyLimitMB      int      `envconfig:"BODY_LIMIT_MB" default:"20"`
	CORSAllowOrigins []string `envconfig:"CORS_ALLOW_ORIGINS" default:"*"`
	CORSAllowMethods []string `envconfig:"CORS_ALLOW_METHODS" default:"*"`
	CORSAllowHeaders []string `envconfig:"CORS_ALLOW_HEADERS" default:"*"`
	// Timeouts default to non-zero values so the server is not exposed to
	// slowloris-style attacks out of the box. Raise WriteTimeout if you stream
	// large responses; set to 0 to disable a given timeout entirely.
	ReadTimeout           time.Duration   `envconfig:"READ_TIMEOUT" default:"15s"`
	WriteTimeout          time.Duration   `envconfig:"WRITE_TIMEOUT" default:"30s"`
	IdleTimeout           time.Duration   `envconfig:"IDLE_TIMEOUT" default:"120s"`
	ErrorHandler          gf.ErrorHandler `ignored:"true"`
	LoggerFormat          string          `envconfig:"LOGGER_FORMAT" default:"{\"time\":\"${time}\",\"ip\":\"${ip}\",\"x-forwarded-for\":\"${reqHeader:X-Forwarded-For}\",\"status\":${status},\"latency\":\"${latency}\",\"method\":\"${method}\",\"path\":\"${path}\",\"error\":\"${error}\"}\n"`
	EnableSecurityHeaders *bool           `envconfig:"ENABLE_SECURITY_HEADERS"`
	SwaggerFilePath       string          `envconfig:"SWAGGER_FILE_PATH"`
}

func (f Fiber) ToSamsaraCfg() fiber.Config {
	return fiber.Config{
		Host:                  f.Host,
		Port:                  f.Port,
		PathPrefix:            f.PathPrefix,
		BodyLimitMB:           f.BodyLimitMB,
		CORSAllowOrigins:      f.CORSAllowOrigins,
		CORSAllowMethods:      f.CORSAllowMethods,
		CORSAllowHeaders:      f.CORSAllowHeaders,
		ReadTimeout:           f.ReadTimeout,
		WriteTimeout:          f.WriteTimeout,
		IdleTimeout:           f.IdleTimeout,
		ErrorHandler:          f.ErrorHandler,
		LoggerFormat:          f.LoggerFormat,
		EnableSecurityHeaders: f.EnableSecurityHeaders,
	}
}
