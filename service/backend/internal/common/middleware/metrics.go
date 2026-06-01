package middleware

import (
	"time"

	gf "github.com/gofiber/fiber/v3"

	"github.com/noircode/backend/internal/common/e"
	"github.com/noircode/backend/internal/common/metrics"
)

// Metrics records request count and latency per method+route. The route label
// is the registered path pattern (e.g. /notes/:id), not the concrete URL, so
// cardinality stays bounded. The status is taken from e.HTTPStatus on error so
// it matches what the central error handler returns (which runs after this
// middleware unwinds).
func Metrics() gf.Handler {
	return func(c gf.Ctx) error {
		start := time.Now()
		err := c.Next()

		route := c.Route().Path
		if route == "" {
			route = "unmatched"
		}
		status := c.Response().StatusCode()
		if err != nil {
			status = e.HTTPStatus(err)
		}
		metrics.ObserveHTTP(c.Method(), route, status, time.Since(start))
		return err
	}
}
