package noircode_test

import (
	"context"
	"strings"
	"testing"

	"github.com/noircode/backend/internal/domain/noircode"
	"github.com/noircode/backend/internal/domain/noircode/model"
)

// fakeImaging records the last Encode call and returns canned bytes.
type fakeImaging struct {
	called bool
	in     model.EncodeInput
}

func (f *fakeImaging) Encode(_ context.Context, in model.EncodeInput) ([]byte, error) {
	f.called = true
	f.in = in
	return []byte("PNG"), nil
}

func (f *fakeImaging) Decode(context.Context, []byte) (model.DecodeResult, error) {
	return model.DecodeResult{}, nil
}

// fakeFetcher is an inert Fetcher for the encode tests (never exercised here).
type fakeFetcher struct{}

func (fakeFetcher) Fetch(context.Context, string) ([]byte, error) {
	return nil, nil
}

func TestEncode_RejectsEmpty(t *testing.T) {
	img := &fakeImaging{}
	d := noircode.New(img, fakeFetcher{})
	if _, err := d.Encode(context.Background(), model.EncodeInput{Text: "  "}); err == nil {
		t.Fatal("expected error for blank text")
	}
	if img.called {
		t.Fatal("imaging should not be called for invalid input")
	}
}

func TestEncode_RejectsTooLong(t *testing.T) {
	img := &fakeImaging{}
	d := noircode.New(img, fakeFetcher{})
	if _, err := d.Encode(context.Background(), model.EncodeInput{Text: strings.Repeat("a", 200)}); err == nil {
		t.Fatal("expected error for oversized text")
	}
	if img.called {
		t.Fatal("imaging should not be called for oversized input")
	}
}

func TestEncode_PassesThroughToImaging(t *testing.T) {
	img := &fakeImaging{}
	d := noircode.New(img, fakeFetcher{})
	png, err := d.Encode(context.Background(), model.EncodeInput{Text: "hello", Style: true})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if string(png) != "PNG" {
		t.Fatalf("expected imaging bytes, got %q", png)
	}
	if !img.called || img.in.Text != "hello" || !img.in.Style {
		t.Fatalf("imaging called with wrong input: %+v", img.in)
	}
}
