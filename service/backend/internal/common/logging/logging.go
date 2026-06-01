// Package logging carries a request-scoped *slog.Logger through context.Context
// so handlers and domain code emit logs correlated by request_id (and user_id).
package logging

import (
	"context"
	"log/slog"
)

type ctxKey struct{}

var key ctxKey

// Into returns a copy of ctx carrying l. The request-ID middleware seeds it with
// a logger bound to the request_id; the auth middleware adds user_id.
func Into(ctx context.Context, l *slog.Logger) context.Context {
	return context.WithValue(ctx, key, l)
}

// From returns the request-scoped logger, or slog.Default() if none is set
// (e.g. on code paths with no inbound request, like the event consumer).
func From(ctx context.Context) *slog.Logger {
	if l, ok := ctx.Value(key).(*slog.Logger); ok && l != nil {
		return l
	}
	return slog.Default()
}
