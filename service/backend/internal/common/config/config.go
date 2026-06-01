package config

import (
	"log"
	"log/slog"

	"github.com/joho/godotenv"
	"github.com/kelseyhightower/envconfig"
)

const (
	localEnvFilePath = "../../env/local/api.env"
	configPrefix     = "NOIRCODE_API"
)

var c *Config

// Init reads config from the environment and caches it. When local is true the
// env file at localEnvFilePath is overlaid first (for running outside Docker).
// Call once from main after parsing flags; subsequent reads use Get.
func Init(local bool) Config {
	cfg := Read(local)
	c = &cfg
	return cfg
}

// Get returns the cached config. Init must be called first.
func Get() Config {
	if c == nil {
		log.Fatal("config: Get called before Init")
	}
	return *c
}

// Read loads config from the environment without caching. Prefer Init/Get;
// Read is exported for tests that need an isolated config.
func Read(local bool) (cfg Config) {
	slog.Info("config reading", "local", local)
	if local {
		if err := godotenv.Overload(localEnvFilePath); err != nil {
			log.Printf("warn: local env file not found (%s): %v — using process env", localEnvFilePath, err)
		}
	}
	if err := envconfig.Process(configPrefix, &cfg); err != nil {
		log.Fatalf("config read from env fail: %v", err)
	}
	slog.Info("config read done")
	return cfg
}
