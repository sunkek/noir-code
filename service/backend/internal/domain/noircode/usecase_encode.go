package noircode

import (
	"context"
	"strings"

	"github.com/sunkek/mishap"

	"github.com/noircode/backend/internal/common/e"
	"github.com/noircode/backend/internal/domain/noircode/model"
)

// maxTextBytes is the hard upper bound the largest grid version can carry; the
// imaging backend enforces the exact per-version capacity, this is a cheap
// early reject for obviously oversized input.
const maxTextBytes = 173

// Encode validates the payload and renders it to a PNG panel via the imaging
// backend.
func (d *Domain) Encode(ctx context.Context, in model.EncodeInput) ([]byte, error) {
	if strings.TrimSpace(in.Text) == "" {
		return nil, mishap.New("text is required", e.Validation)
	}
	if len(in.Text) > maxTextBytes {
		return nil, mishap.New("text too long: max 173 bytes", e.Validation)
	}
	return d.imaging.Encode(ctx, in)
}
