package main

import (
	"fmt"
	"log"
	"net/http"

	"github.com/noircode/backend/internal/common/config"
)

func main() {
	cfg := config.Init(false)
	res, err := http.Get(fmt.Sprintf("http://127.0.0.1:%d/healthz", cfg.Health.Port))
	switch {
	case err != nil:
		log.Fatalf("ERROR: %s\n", err.Error())
	case res.StatusCode != 200 && res.StatusCode != 204:
		log.Fatalf("ERROR: response code is %d\n", res.StatusCode)
	}
}
