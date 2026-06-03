package urlfetch

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"syscall"
	"time"

	"github.com/sunkek/mishap"

	"github.com/noircode/backend/internal/common/e"
)

// errBlocked is returned by the dialer's Control hook when a connection would
// reach a non-public address. It propagates out of http.Client.Do (wrapped in
// *url.Error → *net.OpError), so Fetch can map it to a 403 via errors.Is.
var errBlocked = errors.New("destination address is not allowed")

// Config tunes the fetcher. Zero values fall back to safe defaults.
type Config struct {
	Timeout      time.Duration
	MaxBytes     int64
	MaxRedirects int

	GlobalPerSec float64
	GlobalBurst  float64
	HostPerSec   float64
	HostBurst    float64
}

// Fetcher retrieves a remote image with SSRF protection, a size cap, and
// throttling. It satisfies the noircode domain's Fetcher outbound port.
type Fetcher struct {
	client   *http.Client
	maxBytes int64
	throttle *throttle
}

// New builds a hardened Fetcher. The dialer's Control hook runs after DNS
// resolution with the concrete IP about to be dialed, so it blocks both direct
// private targets and DNS-rebinding / redirect-to-internal attempts on every
// hop and every connection.
func New(cfg Config) *Fetcher {
	if cfg.Timeout <= 0 {
		cfg.Timeout = 8 * time.Second
	}
	if cfg.MaxBytes <= 0 {
		cfg.MaxBytes = 15 << 20
	}
	if cfg.MaxRedirects <= 0 {
		cfg.MaxRedirects = 5
	}

	dialer := &net.Dialer{Timeout: 5 * time.Second, Control: blockNonPublic}
	transport := &http.Transport{
		DialContext:           dialer.DialContext,
		TLSHandshakeTimeout:   5 * time.Second,
		ResponseHeaderTimeout: 5 * time.Second,
		DisableKeepAlives:     true,
		MaxIdleConns:          0,
	}
	client := &http.Client{
		Transport: transport,
		Timeout:   cfg.Timeout,
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			if len(via) >= cfg.MaxRedirects {
				return fmt.Errorf("stopped after %d redirects", cfg.MaxRedirects)
			}
			if !isHTTPScheme(req.URL) {
				return errBlocked
			}
			return nil
		},
	}

	t := newThrottle(cfg.GlobalPerSec, cfg.GlobalBurst, cfg.HostPerSec, cfg.HostBurst)
	go t.janitor()
	return &Fetcher{client: client, maxBytes: cfg.MaxBytes, throttle: t}
}

// Fetch downloads rawURL and returns the body bytes (caller decodes the image).
func (f *Fetcher) Fetch(ctx context.Context, rawURL string) ([]byte, error) {
	u, err := url.Parse(strings.TrimSpace(rawURL))
	if err != nil || !isHTTPScheme(u) {
		return nil, mishap.New("url must be an http(s) address", e.Validation)
	}
	host := strings.ToLower(u.Hostname())
	if host == "" {
		return nil, mishap.New("url has no host", e.Validation)
	}
	// Defense in depth: reject literal private/loopback IPs before any DNS or
	// dial happens (the dialer Control hook is the real enforcement).
	if ip := net.ParseIP(host); ip != nil && !isPublicIP(ip) {
		return nil, mishap.New("url host is not allowed", e.Forbidden)
	}
	if !f.throttle.allow(host) {
		return nil, mishap.New("too many requests for this source; retry shortly", e.RateLimit)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	if err != nil {
		return nil, mishap.Wrap(err, "build fetch request", mishap.WithCode(e.Validation))
	}
	req.Header.Set("User-Agent", "noir-code-decoder/1.0 (+https://noir-code.suncake.xyz)")
	req.Header.Set("Accept", "image/*")

	resp, err := f.client.Do(req)
	if err != nil {
		if errors.Is(err, errBlocked) {
			return nil, mishap.New("url host is not allowed", e.Forbidden)
		}
		return nil, mishap.Wrap(err, "could not fetch the image url", mishap.WithCode(e.Validation))
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, mishap.New(fmt.Sprintf("remote returned status %d", resp.StatusCode), e.Validation)
	}

	// Read at most maxBytes+1 so we can tell "exactly at limit" from "over".
	data, err := io.ReadAll(io.LimitReader(resp.Body, f.maxBytes+1))
	if err != nil {
		return nil, mishap.Wrap(err, "read image body", mishap.WithCode(e.Validation))
	}
	if int64(len(data)) > f.maxBytes {
		return nil, mishap.New("image exceeds the size limit", e.Validation)
	}
	if len(data) == 0 {
		return nil, mishap.New("remote returned an empty body", e.Validation)
	}
	return data, nil
}

func isHTTPScheme(u *url.URL) bool {
	return u != nil && (u.Scheme == "http" || u.Scheme == "https")
}

// blockNonPublic is the dialer Control hook: it rejects any connection whose
// resolved address is not a public, routable unicast IP.
func blockNonPublic(_, address string, _ syscall.RawConn) error {
	host, _, err := net.SplitHostPort(address)
	if err != nil {
		return errBlocked
	}
	ip := net.ParseIP(host)
	if ip == nil || !isPublicIP(ip) {
		return errBlocked
	}
	return nil
}

// isPublicIP reports whether ip is a globally routable unicast address. It
// rejects loopback, RFC1918 / ULA private ranges, link-local (incl. the
// 169.254.169.254 cloud-metadata address), multicast, unspecified, broadcast,
// and the 100.64.0.0/10 carrier-grade NAT range.
func isPublicIP(ip net.IP) bool {
	if ip == nil {
		return false
	}
	if ip4 := ip.To4(); ip4 != nil {
		ip = ip4
	}
	if ip.IsLoopback() || ip.IsPrivate() || ip.IsLinkLocalUnicast() ||
		ip.IsLinkLocalMulticast() || ip.IsMulticast() || ip.IsUnspecified() {
		return false
	}
	if ip4 := ip.To4(); ip4 != nil {
		if ip4.Equal(net.IPv4bcast) {
			return false
		}
		if ip4[0] == 100 && ip4[1] >= 64 && ip4[1] <= 127 { // 100.64.0.0/10 CGNAT
			return false
		}
	}
	return true
}
