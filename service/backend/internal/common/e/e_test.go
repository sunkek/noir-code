package e

import (
	"errors"
	"testing"

	gf "github.com/gofiber/fiber/v3"
	"github.com/sunkek/mishap"
)

func TestHTTPStatus(t *testing.T) {
	tests := []struct {
		name string
		err  error
		want int
	}{
		{"nil", nil, 200},
		{"domain not found", mishap.New("x", NotFound), 404},
		{"rate limit", mishap.New("x", RateLimit), 429},
		// An unknown path or method used to answer 500 (security handoff L3).
		{"fiber no route", gf.ErrNotFound, 404},
		{"fiber wrong method", gf.ErrMethodNotAllowed, 405},
		{"wrapped fiber error", mishap.Wrap(gf.ErrMethodNotAllowed, "ctx"), 405},
		{"unknown", errors.New("boom"), 500},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := HTTPStatus(tt.err); got != tt.want {
				t.Errorf("HTTPStatus = %d, want %d", got, tt.want)
			}
		})
	}
}
