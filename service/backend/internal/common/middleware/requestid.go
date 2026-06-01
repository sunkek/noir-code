package middleware

import (
	"log/slog"

	gf "github.com/gofiber/fiber/v3"
	"github.com/google/uuid"

	"github.com/noircode/backend/internal/common/logging"
)

// HeaderRequestID is the inbound/outbound correlation header.
const HeaderRequestID = "X-Request-ID"

// RequestID assigns each request a correlation id (honouring an inbound
// X-Request-ID, otherwise generating one), echoes it in the response, and seeds
// a request-scoped logger bound to request_id into the context. Downstream code
// retrieves it with logging.From(ctx.Context()). Register this before the auth
// middleware so every request — authenticated or not — is correlated.
func RequestID(base *slog.Logger) gf.Handler {
	return func(c gf.Ctx) error {
		id := c.Get(HeaderRequestID)
		if id == "" {
			id = uuid.NewString()
		}
		c.Set(HeaderRequestID, id)
		l := base.With("request_id", id)
		c.SetContext(logging.Into(c.Context(), l))
		return c.Next()
	}
}
