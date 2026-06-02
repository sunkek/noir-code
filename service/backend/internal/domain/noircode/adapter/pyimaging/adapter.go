// Package pyimaging implements the noircode.Imaging outbound port by calling the
// Python imaging sidecar over HTTP. The sidecar owns the OpenCV encode/decode
// pipeline (the NoiR Code reference implementation).
package pyimaging

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"time"

	"github.com/sunkek/mishap"

	"github.com/noircode/backend/internal/common/e"
	"github.com/noircode/backend/internal/domain/noircode/model"
)

// Adapter is an HTTP client for the imaging sidecar.
type Adapter struct {
	baseURL string
	client  *http.Client
}

// New builds the adapter. baseURL is the sidecar root (e.g. http://imaging:8001).
func New(baseURL string, timeout time.Duration) *Adapter {
	return &Adapter{
		baseURL: baseURL,
		client:  &http.Client{Timeout: timeout},
	}
}

type encodeReq struct {
	Text      string  `json:"text"`
	Style     bool    `json:"style"`
	HatchData bool    `json:"hatch_data"`
	Adaptive  bool    `json:"adaptive"`
	Caption   *string `json:"caption,omitempty"`
}

type errBody struct {
	Detail string `json:"detail"`
}

// Encode posts the encode request and returns the PNG bytes.
func (a *Adapter) Encode(ctx context.Context, in model.EncodeInput) ([]byte, error) {
	body, err := json.Marshal(encodeReq{
		Text:      in.Text,
		Style:     in.Style,
		HatchData: in.HatchData,
		Adaptive:  in.Adaptive,
		Caption:   in.Caption,
	})
	if err != nil {
		return nil, mishap.Wrap(err, "marshal encode request")
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, a.baseURL+"/encode", bytes.NewReader(body))
	if err != nil {
		return nil, mishap.Wrap(err, "build encode request")
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := a.client.Do(req)
	if err != nil {
		return nil, mishap.Wrap(err, "call imaging encode", mishap.WithCode(e.Internal))
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, sidecarError(resp, "encode")
	}
	png, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, mishap.Wrap(err, "read encode response", mishap.WithCode(e.Internal))
	}
	return png, nil
}

// Decode posts the image as multipart and parses the decode result.
func (a *Adapter) Decode(ctx context.Context, image []byte) (model.DecodeResult, error) {
	var buf bytes.Buffer
	mw := multipart.NewWriter(&buf)
	part, err := mw.CreateFormFile("image", "panel.png")
	if err != nil {
		return model.DecodeResult{}, mishap.Wrap(err, "build multipart")
	}
	if _, err := part.Write(image); err != nil {
		return model.DecodeResult{}, mishap.Wrap(err, "write multipart image")
	}
	if err := mw.Close(); err != nil {
		return model.DecodeResult{}, mishap.Wrap(err, "close multipart")
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, a.baseURL+"/decode", &buf)
	if err != nil {
		return model.DecodeResult{}, mishap.Wrap(err, "build decode request")
	}
	req.Header.Set("Content-Type", mw.FormDataContentType())

	resp, err := a.client.Do(req)
	if err != nil {
		return model.DecodeResult{}, mishap.Wrap(err, "call imaging decode", mishap.WithCode(e.Internal))
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return model.DecodeResult{}, sidecarError(resp, "decode")
	}
	var out model.DecodeResult
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return model.DecodeResult{}, mishap.Wrap(err, "parse decode response", mishap.WithCode(e.Internal))
	}
	return out, nil
}

// sidecarError maps a non-200 sidecar response to a domain error. A 4xx becomes
// a validation error (client's fault — bad text/image); anything else is internal.
func sidecarError(resp *http.Response, op string) error {
	var eb errBody
	_ = json.NewDecoder(resp.Body).Decode(&eb)
	detail := eb.Detail
	if detail == "" {
		detail = fmt.Sprintf("imaging %s failed: status %d", op, resp.StatusCode)
	}
	if resp.StatusCode >= 400 && resp.StatusCode < 500 {
		return mishap.New(detail, e.Validation)
	}
	return mishap.New(detail, e.Internal)
}
