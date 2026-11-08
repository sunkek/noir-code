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
// Every proxy APPENDS the peer it saw to X-Forwarded-For. Our own proxies
// append exactly ownHops entries: Traefik appends its peer (the Cloudflare
// edge, or cloudflared once ingress runs through a Cloudflare Tunnel) and nginx
// appends Traefik. So whatever the topology the header ends
// "<client>, <traefik's peer>, <traefik>", and the client is the entry just
// left of those two. Anything a caller forges, including from a Cloudflare
// Worker, sits further left and is never read. (agora's clientip.Resolve with
// depth 3 is the same rule.)
//
// A header with fewer entries did not come through the full chain: dev
// (nginx only), or a request that reached Traefik directly from an untrusted
// peer, which Traefik rewrites to just that peer. Those fall back to the socket
// address, a coarse shared bucket rather than a guess.
func ClientIP(c gf.Ctx) string {
	if ip, ok := publicClientFromXFF(c.Get("X-Forwarded-For")); ok {
		return ip
	}
	return c.IP()
}

// ownHops is how many X-Forwarded-For entries our own proxies append.
const ownHops = 2

// publicClientFromXFF returns the client entry of an X-Forwarded-For value as
// described on ClientIP, or ok=false if there is none or it is not public.
func publicClientFromXFF(xff string) (string, bool) {
	if strings.TrimSpace(xff) == "" {
		return "", false
	}
	parts := strings.Split(xff, ",")
	idx := len(parts) - 1 - ownHops
	if idx < 0 {
		return "", false
	}
	ip := net.ParseIP(strings.TrimSpace(parts[idx]))
	if ip == nil || !isPublicIP(ip) {
		return "", false
	}
	return bucket(ip), true
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
