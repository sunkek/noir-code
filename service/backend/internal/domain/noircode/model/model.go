// Package model holds the noircode domain's data types. They live here so both
// the domain layer and its adapters can reference them without an import cycle.
package model

// EncodeInput is the parameter object for encoding text into a NoiR Code panel.
// The flags mirror the Python reference CLI / sidecar.
type EncodeInput struct {
	Text      string
	Style     bool // noir styling + halftone artwork
	HatchData bool // render data cells as line hatching (engraving look)
	Adaptive  bool // shrink the grid to the smallest size that fits the text
}

// DecodeResult is the structured outcome of decoding a panel image. It mirrors
// the Python decoder's DecodeResult; pointer fields are nil when not available.
type DecodeResult struct {
	OK            bool    `json:"ok"`
	Text          *string `json:"text"`
	Confidence    float64 `json:"confidence"`
	Rotation      *int    `json:"rotation"`
	GridErasures  int     `json:"grid_erasures"`
	MotifErasures int     `json:"motif_erasures"`
	CrossCheck    *bool   `json:"cross_check"`
	FailedStage   *string `json:"failed_stage"`
}
