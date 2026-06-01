package main

import (
	"context"
	"flag"
	"log/slog"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/noircode/backend/internal/common/config"
	"github.com/noircode/backend/internal/common/e"
	"github.com/noircode/backend/internal/common/metrics"
	"github.com/noircode/backend/internal/common/middleware"
	"github.com/noircode/backend/internal/domain/noircode"
	noircodefiber "github.com/noircode/backend/internal/domain/noircode/adapter/fiber"
	"github.com/noircode/backend/internal/domain/noircode/adapter/pyimaging"

	"github.com/gofiber/contrib/v3/swaggo"
	gf "github.com/gofiber/fiber/v3"
	"github.com/gofiber/fiber/v3/middleware/adaptor"
	"github.com/gofiber/fiber/v3/middleware/static"
	"github.com/sunkek/samsara"
	"github.com/sunkek/samsara-components/fiber"
)

// @Title						NoiR Code API
// @Version					0.1
// @Description				Encode text into a NoiR Code panel and decode panels back to text.
// @Contact.name				Sunkek
// @BasePath					/api/v1
func main() {
	local := flag.Bool("l", false, "load env/local/api.env for running outside Docker")
	flag.Parse()
	cfg := config.Init(*local)
	cfg.Fiber.ErrorHandler = func(ctx gf.Ctx, err error) error {
		// Status mapping lives in e.HTTPStatus so the metrics middleware can label
		// error responses with the same code the client receives.
		return ctx.Status(e.HTTPStatus(err)).JSON(gf.Map{"error": err.Error()})
	}
	logger := slog.New(slog.NewJSONHandler(
		os.Stderr,
		&slog.HandlerOptions{
			Level:     slog.Level(cfg.Log.Level),
			AddSource: cfg.Log.Source,
		},
	))
	slog.SetDefault(logger)

	// Warn loudly if CORS is left wide open. Set explicit origins via
	// NOIRCODE_API_FIBER_CORS_ALLOW_ORIGINS in stage/prod.
	for _, o := range cfg.Fiber.CORSAllowOrigins {
		if strings.TrimSpace(o) == "*" {
			logger.Warn("CORS allows all origins (*) — set explicit origins for production")
			break
		}
	}

	sup := samsara.NewSupervisor(
		samsara.WithSupervisorLogger(logger),
		samsara.WithMetricsObserver(metrics.NewObserver()),
		samsara.WithHealthInterval(cfg.Health.Interval),
		samsara.WithEventHooks(&samsara.EventHooks{
			OnUnhealthy: func(component string, err error) {
				logger.Error("component unhealthy", "component", component, "error", err)
			},
			OnRecovered: func(component string) {
				logger.Info("component recovered", "component", component)
			},
			OnFailed: func(component string, err error) {
				logger.Error("component permanently failed", "component", component, "error", err)
			},
		}),
	)

	hs := samsara.NewHealthServer(
		sup,
		samsara.WithHealthLogger(logger),
		samsara.WithHealthName("health"),
		samsara.WithHealthAddr(":"+strconv.Itoa(cfg.Health.Port)),
	)
	sup.Add(hs, samsara.WithTier(samsara.TierCritical))

	// The gateway is stateless: no DB/broker/cache. The only HTTP edge is fiber;
	// the encode/decode work is delegated to the imaging sidecar over HTTP.
	fiberCmp := fiber.New(cfg.Fiber.ToSamsaraCfg(), fiber.WithLogger(logger), fiber.WithName("fiber"))

	// Correlate every request: assign/propagate X-Request-ID and seed a
	// request-scoped logger. Registered first so all routes are covered.
	fiberCmp.Use(middleware.RequestID(logger))
	// Record request count/latency per method+route.
	fiberCmp.Use(middleware.Metrics())
	// Throttle the public encode/decode endpoints per client IP.
	fiberCmp.Use(middleware.RateLimit(middleware.RateLimitConfig{
		Max:    cfg.RateLimit.Max,
		Window: cfg.RateLimit.Window,
	}))
	// Expose Prometheus metrics. Public (scraped without a token); in production
	// bind it to an internal network/port rather than the public ingress.
	fiberCmp.Register(func(r gf.Router) {
		r.Get("/metrics", adaptor.HTTPHandler(metrics.Handler()))
	})

	if cfg.Fiber.SwaggerFilePath != "" {
		fiberCmp.Use(cfg.Fiber.PathPrefix+"/docs/swagger.json", static.New(cfg.Fiber.SwaggerFilePath))
		fiberCmp.Register(func(r gf.Router) {
			r.Get("/docs/*", swaggo.New(swaggo.Config{
				URL: cfg.Fiber.PathPrefix + "/docs/swagger.json",
			}))
			r.Get("/", func(ctx gf.Ctx) error {
				return ctx.Redirect().To(cfg.Fiber.PathPrefix + "/docs")
			})
		})
	}

	sup.Add(fiberCmp,
		samsara.WithTier(samsara.TierCritical),
		samsara.WithRestartPolicy(samsara.MaxRetries(5, 5*time.Second)),
	)

	// noircode: the only domain. Build imaging adapter (HTTP client to the Python
	// sidecar) → domain → REST adapter. Wiring is compile-time checked.
	imaging := pyimaging.New(cfg.Imaging.BaseURL, cfg.Imaging.Timeout)
	noircodeDomain := noircode.New(imaging)
	_ = noircodefiber.New(fiberCmp, noircodeDomain)

	app := samsara.NewApplication(
		samsara.WithSupervisor(sup),
		samsara.WithLogger(logger),
		samsara.WithShutdownTimeout(30*time.Second),
		samsara.WithMainFunc(func(ctx context.Context) error {
			<-ctx.Done()
			return nil
		}),
	)

	if err := app.Run(); err != nil {
		logger.Error("application exited with error", "error", err)
		os.Exit(1)
	}
}
