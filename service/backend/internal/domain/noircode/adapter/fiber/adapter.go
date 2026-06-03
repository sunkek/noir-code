// Package fiber exposes the noircode domain over HTTP.
package fiber

import (
	"io"

	gf "github.com/gofiber/fiber/v3"
	"github.com/sunkek/mishap"
	fibercmp "github.com/sunkek/samsara-components/fiber"

	"github.com/noircode/backend/internal/common/e"
	"github.com/noircode/backend/internal/domain/noircode"
	"github.com/noircode/backend/internal/domain/noircode/model"
)

// Adapter wires the noircode domain's inbound port to Fiber routes.
type Adapter struct {
	svc noircode.Service
}

// New registers the encode/decode routes on the fiber component.
func New(f *fibercmp.Component, svc noircode.Service) *Adapter {
	a := &Adapter{svc: svc}
	f.Register(func(r gf.Router) {
		r.Post("/encode", a.handleEncode)
		r.Post("/decode", a.handleDecode)
		r.Post("/decode-url", a.handleDecodeURL)
	})
	return a
}

type encodeReq struct {
	Text      string `json:"text"`
	Style     bool   `json:"style"`
	HatchData bool   `json:"hatch_data"`
	// Adaptive defaults to true (smaller panel for short text). Send false to
	// force the full fixed grid.
	Adaptive *bool `json:"adaptive"`
	// Caption stamped under the panel. Omit to use the server default; send an
	// empty string to disable the caption.
	Caption *string `json:"caption,omitempty"`
}

// handleEncode godoc
//
//	@Summary	Encode text into a NoiR Code panel
//	@Tags		noircode
//	@Accept		json
//	@Produce	png
//	@Param		body	body	encodeReq	true	"encode options"
//	@Success	200		{file}	binary
//	@Router		/encode [post]
func (a *Adapter) handleEncode(ctx gf.Ctx) error {
	var req encodeReq
	if err := ctx.Bind().Body(&req); err != nil {
		return mishap.Wrap(err, "bind body", mishap.WithCode(e.Validation))
	}
	adaptive := true
	if req.Adaptive != nil {
		adaptive = *req.Adaptive
	}
	png, err := a.svc.Encode(ctx.Context(), model.EncodeInput{
		Text:      req.Text,
		Style:     req.Style,
		HatchData: req.HatchData,
		Adaptive:  adaptive,
		Caption:   req.Caption,
	})
	if err != nil {
		return err
	}
	ctx.Set("Content-Type", "image/png")
	return ctx.Send(png)
}

// handleDecode godoc
//
//	@Summary	Decode a NoiR Code panel image to text
//	@Tags		noircode
//	@Accept		multipart/form-data
//	@Produce	json
//	@Param		image	formData	file	true	"panel image (PNG/JPEG)"
//	@Success	200		{object}	model.DecodeResult
//	@Router		/decode [post]
func (a *Adapter) handleDecode(ctx gf.Ctx) error {
	fh, err := ctx.FormFile("image")
	if err != nil {
		return mishap.New("missing 'image' file field", e.Validation)
	}
	f, err := fh.Open()
	if err != nil {
		return mishap.Wrap(err, "open upload", mishap.WithCode(e.Validation))
	}
	defer f.Close()
	data, err := io.ReadAll(f)
	if err != nil {
		return mishap.Wrap(err, "read upload", mishap.WithCode(e.Validation))
	}
	res, err := a.svc.Decode(ctx.Context(), data)
	if err != nil {
		return err
	}
	return ctx.JSON(res)
}

type decodeURLReq struct {
	URL string `json:"url"`
}

// handleDecodeURL godoc
//
//	@Summary	Decode a NoiR Code panel from a remote image URL
//	@Tags		noircode
//	@Accept		json
//	@Produce	json
//	@Param		body	body		decodeURLReq	true	"image url"
//	@Success	200		{object}	model.DecodeResult
//	@Router		/decode-url [post]
func (a *Adapter) handleDecodeURL(ctx gf.Ctx) error {
	var req decodeURLReq
	if err := ctx.Bind().Body(&req); err != nil {
		return mishap.Wrap(err, "bind body", mishap.WithCode(e.Validation))
	}
	res, err := a.svc.DecodeURL(ctx.Context(), req.URL)
	if err != nil {
		return err
	}
	return ctx.JSON(res)
}
