package urlfetch

import (
	"context"
	"net"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/sunkek/mishap"

	"github.com/noircode/backend/internal/common/e"
)

func TestIsPublicIP(t *testing.T) {
	cases := map[string]bool{
		"8.8.8.8":              true,
		"1.1.1.1":              true,
		"2606:4700:4700::1111": true,
		"10.0.0.1":             false, // RFC1918
		"172.16.5.4":           false, // RFC1918
		"192.168.1.1":          false, // RFC1918
		"127.0.0.1":            false, // loopback
		"169.254.169.254":      false, // link-local / cloud metadata
		"0.0.0.0":              false, // unspecified
		"255.255.255.255":      false, // broadcast
		"100.64.0.1":           false, // CGNAT
		"224.0.0.1":            false, // multicast
		"::1":                  false, // loopback v6
		"fe80::1":              false, // link-local v6
		"fc00::1":              false, // ULA v6
	}
	for s, want := range cases {
		ip := net.ParseIP(s)
		if ip == nil {
			t.Fatalf("bad test ip %q", s)
		}
		if got := isPublicIP(ip); got != want {
			t.Errorf("isPublicIP(%s) = %v, want %v", s, got, want)
		}
	}
}

func codeOf(t *testing.T, err error) mishap.Code {
	t.Helper()
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	m, ok := mishap.As(err)
	if !ok {
		t.Fatalf("error is not a mishap: %v", err)
	}
	return m.Code()
}

func TestFetch_Rejections(t *testing.T) {
	f := New(Config{GlobalPerSec: 100, GlobalBurst: 100, HostPerSec: 100, HostBurst: 100})
	ctx := context.Background()

	if got := codeOf(t, mustErr(f.Fetch(ctx, "ftp://example.com/x.png"))); got != e.Validation {
		t.Errorf("ftp scheme: got %v, want Validation", got)
	}
	if got := codeOf(t, mustErr(f.Fetch(ctx, "not a url"))); got != e.Validation {
		t.Errorf("garbage url: got %v, want Validation", got)
	}
	// Literal private/loopback IPs are rejected before any dial.
	if got := codeOf(t, mustErr(f.Fetch(ctx, "http://127.0.0.1/x.png"))); got != e.Forbidden {
		t.Errorf("loopback literal: got %v, want Forbidden", got)
	}
	if got := codeOf(t, mustErr(f.Fetch(ctx, "http://169.254.169.254/latest/meta-data/"))); got != e.Forbidden {
		t.Errorf("metadata literal: got %v, want Forbidden", got)
	}
}

// TestFetch_LoopbackServerBlocked confirms a real loopback server cannot be
// reached even though it is a live HTTP endpoint.
func TestFetch_LoopbackServerBlocked(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte("secret"))
	}))
	defer srv.Close()

	f := New(Config{GlobalPerSec: 100, GlobalBurst: 100, HostPerSec: 100, HostBurst: 100})
	if got := codeOf(t, mustErr(f.Fetch(context.Background(), srv.URL))); got != e.Forbidden {
		t.Errorf("loopback server: got %v, want Forbidden", got)
	}
}

func TestThrottle_Global(t *testing.T) {
	// rate 0 → no refill during the test; capacity 2 → exactly two allowed.
	th := newThrottle(0, 2, 0, 100)
	if !th.allow("a") || !th.allow("b") {
		t.Fatal("first two global tokens should be allowed")
	}
	if th.allow("c") {
		t.Fatal("global budget exhausted; third should be denied")
	}
}

func TestThrottle_PerHost(t *testing.T) {
	th := newThrottle(0, 100, 0, 1) // generous global, per-host cap 1
	if !th.allow("a.com") {
		t.Fatal("first request to host should be allowed")
	}
	if th.allow("a.com") {
		t.Fatal("second request to same host should be denied")
	}
	if !th.allow("b.com") {
		t.Fatal("different host should be allowed")
	}
}

func TestThrottle_Refill(t *testing.T) {
	th := newThrottle(0, 100, 1000, 1) // host refills fast (1000/s)
	if !th.allow("h") {
		t.Fatal("first allowed")
	}
	if th.allow("h") {
		t.Fatal("immediate second denied")
	}
	time.Sleep(5 * time.Millisecond) // ~5 tokens refilled
	if !th.allow("h") {
		t.Fatal("after refill should be allowed")
	}
}

func mustErr(_ []byte, err error) error { return err }
