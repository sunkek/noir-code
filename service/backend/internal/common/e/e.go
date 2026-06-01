package e

import "github.com/sunkek/mishap"

const (
	Conflict   = mishap.Code("ERR_CONFLICT")
	Forbidden  = mishap.Code("ERR_FORBIDDEN")
	Internal   = mishap.Code("ERR_INTERNAL")
	JWT        = mishap.Code("ERR_JWT_PROCESSING")
	NotFound   = mishap.Code("ERR_NOT_FOUND")
	RateLimit  = mishap.Code("ERR_RATE_LIMIT")
	Validation = mishap.Code("ERR_VALIDATION")
)

// HTTPStatus maps an error to an HTTP status code. It is the single source of
// truth shared by the Fiber error handler and the metrics middleware. A nil
// error maps to 200; an unrecognised error to 500.
func HTTPStatus(err error) int {
	if err == nil {
		return 200
	}
	if m, ok := mishap.As(err); ok {
		switch m.Code() {
		case NotFound:
			return 404
		case Conflict:
			return 409
		case Validation:
			return 400
		case Forbidden:
			return 403
		case JWT:
			return 401
		case RateLimit:
			return 429
		}
	}
	return 500
}
