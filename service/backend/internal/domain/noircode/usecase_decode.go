package noircode

import (
	"context"

	"github.com/sunkek/mishap"

	"github.com/noircode/backend/internal/common/e"
	"github.com/noircode/backend/internal/domain/noircode/model"
)

// Decode reads a panel image (PNG/JPEG bytes) and returns the decode result.
// A failed decode is NOT an error: it returns a DecodeResult with OK=false and
// FailedStage set, so the client can show a diagnostic rather than a 500.
func (d *Domain) Decode(ctx context.Context, image []byte) (model.DecodeResult, error) {
	if len(image) == 0 {
		return model.DecodeResult{}, mishap.New("image is required", e.Validation)
	}
	return d.imaging.Decode(ctx, image)
}
