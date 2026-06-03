package middleware

import (
	"net"
	"strings"

	gf "github.com/gofiber/fiber/v3"
)

// ClientIP resolves the real client IP behind trusted reverse proxies in a
// spoof-resistant way, for use as a RateLimit KeyFunc.
//
// The deployment chain is client → Traefik → nginx → backend. Every infra hop
// sits on a private IP range and APPENDS to X-Forwarded-For, so the header
// arriving here looks like "<client>, <traefik>" — and a client that injects
// its own X-Forwarded-For only prepends entries to the LEFT of the address
// Traefik observed. The genuine client is therefore the right-most PUBLIC entry
// (private proxy hops are skipped from the right; anything the client forged
// stays to the left of the real address and is ignored).
//
// Falls back to the socket remote address when no public entry exists (e.g.
// direct in-cluster calls), which keys such callers by their private IP.
func ClientIP(c gf.Ctx) string {
	if ip, ok := publicClientFromXFF(c.Get("X-Forwarded-For")); ok {
		return ip
	}
	return c.IP()
}

// publicClientFromXFF returns the right-most public IP in an X-Forwarded-For
// value, or ok=false if there is none.
func publicClientFromXFF(xff string) (string, bool) {
	if xff == "" {
		return "", false
	}
	parts := strings.Split(xff, ",")
	for i := len(parts) - 1; i >= 0; i-- {
		ip := net.ParseIP(strings.TrimSpace(parts[i]))
		if ip != nil && isPublicIP(ip) {
			return ip.String(), true
		}
	}
	return "", false
}

// isPublicIP reports whether ip is a globally routable unicast address.
func isPublicIP(ip net.IP) bool {
	if ip4 := ip.To4(); ip4 != nil {
		ip = ip4
	}
	return !(ip.IsLoopback() || ip.IsPrivate() || ip.IsLinkLocalUnicast() ||
		ip.IsLinkLocalMulticast() || ip.IsMulticast() || ip.IsUnspecified())
}
