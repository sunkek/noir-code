// Package middleware holds cross-cutting Fiber middleware that is not owned by
// any single domain.
package middleware

import (
	"strconv"
	"sync"
	"time"

	gf "github.com/gofiber/fiber/v3"
	"github.com/sunkek/mishap"

	"github.com/noircode/backend/internal/common/e"
)

// RateLimitConfig configures a fixed-window per-client rate limiter.
type RateLimitConfig struct {
	// Max is the number of requests allowed per Window per client key.
	Max int
	// Window is the length of the fixed window.
	Window time.Duration
	// KeyFunc derives the client key from the request. Defaults to the client
	// IP (gf.Ctx.IP) when nil.
	KeyFunc func(gf.Ctx) string
}

type counter struct {
	count   int
	resetAt time.Time
}

type rateLimiter struct {
	mu      sync.Mutex
	clients map[string]*counter
	max     int
	window  time.Duration
	keyFn   func(gf.Ctx) string
}

// RateLimit returns a Fiber middleware that allows at most cfg.Max requests per
// cfg.Window per client key, returning an e.RateLimit error (→ HTTP 429) once
// the limit is exceeded. State is in-process: it protects a single backend
// instance and resets on restart. For multiple replicas, back the counter with
// a shared store (Redis is already wired in main).
func RateLimit(cfg RateLimitConfig) gf.Handler {
	if cfg.Max <= 0 {
		cfg.Max = 10
	}
	if cfg.Window <= 0 {
		cfg.Window = time.Minute
	}
	keyFn := cfg.KeyFunc
	if keyFn == nil {
		keyFn = func(c gf.Ctx) string { return c.IP() }
	}
	rl := &rateLimiter{
		clients: make(map[string]*counter),
		max:     cfg.Max,
		window:  cfg.Window,
		keyFn:   keyFn,
	}
	go rl.janitor()
	return rl.handle
}

func (rl *rateLimiter) handle(c gf.Ctx) error {
	key := rl.keyFn(c)
	now := time.Now()

	rl.mu.Lock()
	cl, ok := rl.clients[key]
	if !ok || now.After(cl.resetAt) {
		cl = &counter{resetAt: now.Add(rl.window)}
		rl.clients[key] = cl
	}
	cl.count++
	count, resetAt := cl.count, cl.resetAt
	rl.mu.Unlock()

	if count > rl.max {
		retry := int(time.Until(resetAt).Seconds()) + 1
		c.Set("Retry-After", strconv.Itoa(retry))
		return mishap.New("rate limit exceeded, retry later", e.RateLimit)
	}
	return c.Next()
}

// janitor periodically drops expired entries so the map does not grow without
// bound under churning client keys.
func (rl *rateLimiter) janitor() {
	ticker := time.NewTicker(rl.window)
	defer ticker.Stop()
	for range ticker.C {
		now := time.Now()
		rl.mu.Lock()
		for k, cl := range rl.clients {
			if now.After(cl.resetAt) {
				delete(rl.clients, k)
			}
		}
		rl.mu.Unlock()
	}
}
