package noircode

import (
	"context"
	"strings"

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

// DecodeURL fetches an image from a remote URL (with the Fetcher's egress
// safeguards) and decodes it. Fetch failures surface as validation/forbidden/
// rate-limit errors; a clean fetch that simply does not decode returns an
// OK=false result like Decode.
func (d *Domain) DecodeURL(ctx context.Context, url string) (model.DecodeResult, error) {
	if strings.TrimSpace(url) == "" {
		return model.DecodeResult{}, mishap.New("url is required", e.Validation)
	}
	image, err := d.fetcher.Fetch(ctx, url)
	if err != nil {
		return model.DecodeResult{}, err
	}
	return d.Decode(ctx, image)
}
