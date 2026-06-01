package noircode

import (
	"context"

	"github.com/noircode/backend/internal/domain/noircode/model"
)

// Service is the inbound port: the use cases the REST adapter calls. *Domain
// implements it, so the dependency points adapter → domain (never the reverse).
type Service interface {
	// Encode renders text into a NoiR Code panel and returns the PNG bytes.
	Encode(ctx context.Context, in model.EncodeInput) ([]byte, error)
	// Decode reads a panel image and returns the decoded text + diagnostics.
	Decode(ctx context.Context, image []byte) (model.DecodeResult, error)
}

// Imaging is the outbound port: the actual encode/decode work, delegated to the
// Python reference implementation (it owns the OpenCV pipeline). The pyimaging
// HTTP adapter implements it.
type Imaging interface {
	Encode(ctx context.Context, in model.EncodeInput) ([]byte, error)
	Decode(ctx context.Context, image []byte) (model.DecodeResult, error)
}
