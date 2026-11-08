package middleware

import "testing"

func TestPublicClientFromXFF(t *testing.T) {
	cases := []struct {
		name string
		xff  string
		want string
		ok   bool
	}{
		{"empty", "", "", false},
		// Today: client, Cloudflare edge (Traefik's peer), Traefik (nginx's peer).
		{"via cloudflare edge", "203.0.113.7, 172.70.1.2, 172.21.0.2", "203.0.113.7", true},
		// Through a Cloudflare Tunnel: Traefik's peer is cloudflared, private.
		{"via tunnel", "203.0.113.7, 172.19.0.9, 172.21.0.2", "203.0.113.7", true},
		// Forged entries sit left of the client and are never read.
		{"spoof prepended", "1.2.3.4, 203.0.113.7, 172.70.1.2, 172.21.0.2", "203.0.113.7", true},
		{"spoof many", "9.9.9.9, 8.8.8.8, 203.0.113.7, 172.19.0.9, 172.21.0.2", "203.0.113.7", true},
		// A Cloudflare Worker's egress address is the client, not a hop to skip.
		{"worker via edge", "1.2.3.4, 104.16.5.5, 172.70.1.2, 172.21.0.2", "104.16.5.5", true},
		{"worker via tunnel", "1.2.3.4, 104.16.5.5, 172.19.0.9, 172.21.0.2", "104.16.5.5", true},
		// Too short to have come through the full chain: dev (nginx only), or
		// Traefik reached directly from an untrusted peer.
		{"nginx only", "203.0.113.7", "", false},
		{"direct to traefik", "203.0.113.7, 172.21.0.2", "", false},
		// The client slot holding a non-public or garbage value is not a client.
		{"private client slot", "10.0.0.5, 172.19.0.9, 172.21.0.2", "", false},
		{"garbage client slot", "not-an-ip, 172.19.0.9, 172.21.0.2", "", false},
		{"metadata client slot", "169.254.169.254, 172.19.0.9, 172.21.0.2", "", false},
		// IPv6: bucketed by /64, so rotating inside one allocation is free.
		{"v6", "2001:db8::7, 2a06:98c1::1, 172.21.0.2", "2001:db8::/64", true},
		{"v6 same /64", "2001:db8:0:0:dead:beef:1:2, 172.19.0.9, 172.21.0.2", "2001:db8::/64", true},
		{"v6 other /64", "2001:db8:0:1::7, 172.19.0.9, 172.21.0.2", "2001:db8:0:1::/64", true},
		{"v4-mapped", "::ffff:203.0.113.7, 172.19.0.9, 172.21.0.2", "203.0.113.7", true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, ok := publicClientFromXFF(tc.xff)
			if got != tc.want || ok != tc.ok {
				t.Errorf("publicClientFromXFF(%q) = (%q, %v), want (%q, %v)", tc.xff, got, ok, tc.want, tc.ok)
			}
		})
	}
}
