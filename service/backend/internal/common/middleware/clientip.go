package middleware

import (
	"net"
	"strings"

	gf "github.com/gofiber/fiber/v3"
)

// ClientIP resolves the real client behind trusted reverse proxies in a
// spoof-resistant way, for use as a RateLimit KeyFunc. It returns a bucket key:
// the IPv4 address, or the IPv6 /64 (see bucket).
//
// The deployment chain is client → Cloudflare → Traefik → nginx → backend.
// Every hop APPENDS the peer it saw to X-Forwarded-For, so the header arriving
// here reads "<client>, <cloudflare edge>, <traefik>" — and a client that
// injects its own X-Forwarded-For only prepends entries to the LEFT of the
// address Cloudflare observed. The genuine client is therefore the entry just
// left of our hops: private addresses (Traefik, nginx) are skipped from the
// right, then at most ONE Cloudflare address (the edge node Traefik saw), and
// the next entry is the client — even if it is itself a Cloudflare address.
//
// Skipping the edge matters: without it every visitor routed through one PoP
// shares a single rate-limit bucket. Skipping only one matters too: a request
// sent from a Cloudflare Worker egresses from a Cloudflare address, so
// "forged, <worker>, <edge>, <traefik>" must resolve to the worker, not walk
// on into the forged entries. The same walk stays correct without Cloudflare in
// front (dev, or a request that reached Traefik directly — Traefik does not
// trust XFF from non-Cloudflare peers and replaces it with the real peer).
//
// Falls back to the socket remote address when no public entry exists (e.g.
// direct in-cluster calls), which keys such callers by their private IP.
func ClientIP(c gf.Ctx) string {
	if ip, ok := publicClientFromXFF(c.Get("X-Forwarded-For")); ok {
		return ip
	}
	return c.IP()
}

// publicClientFromXFF returns the client entry of an X-Forwarded-For value as
// described on ClientIP, or ok=false if there is none.
func publicClientFromXFF(xff string) (string, bool) {
	if xff == "" {
		return "", false
	}
	parts := strings.Split(xff, ",")
	skippedEdge := false
	for i := len(parts) - 1; i >= 0; i-- {
		ip := net.ParseIP(strings.TrimSpace(parts[i]))
		if ip == nil || !isPublicIP(ip) {
			continue // our own private hops
		}
		if !skippedEdge && isCloudflare(ip) {
			skippedEdge = true // the edge node Traefik received from
			continue
		}
		return bucket(ip), true
	}
	return "", false
}

// bucket returns the rate-limit identity for a client address: the address
// itself for IPv4, its /64 for IPv6. One IPv6 subscriber or VPS normally holds a
// whole /64, so keying on the full address would hand an attacker 2^64 fresh
// buckets.
func bucket(ip net.IP) string {
	if ip.To4() != nil {
		return ip.String()
	}
	return (&net.IPNet{IP: ip.Mask(net.CIDRMask(64, 128)), Mask: net.CIDRMask(64, 128)}).String()
}

// isPublicIP reports whether ip is a globally routable unicast address.
func isPublicIP(ip net.IP) bool {
	if ip4 := ip.To4(); ip4 != nil {
		ip = ip4
	}
	return !(ip.IsLoopback() || ip.IsPrivate() || ip.IsLinkLocalUnicast() ||
		ip.IsLinkLocalMulticast() || ip.IsMulticast() || ip.IsUnspecified())
}

// cloudflareRanges are Cloudflare's edge ranges (https://www.cloudflare.com/ips/),
// the same list Traefik's forwardedHeaders.trustedIPs uses on the host. They
// change rarely; keep the two in step.
var cloudflareRanges = mustParseCIDRs(
	"173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
	"141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
	"197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
	"104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
	"2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32",
	"2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32",
)

func isCloudflare(ip net.IP) bool {
	for _, n := range cloudflareRanges {
		if n.Contains(ip) {
			return true
		}
	}
	return false
}

func mustParseCIDRs(cidrs ...string) []*net.IPNet {
	out := make([]*net.IPNet, 0, len(cidrs))
	for _, c := range cidrs {
		_, n, err := net.ParseCIDR(c)
		if err != nil {
			panic(err)
		}
		out = append(out, n)
	}
	return out
}
