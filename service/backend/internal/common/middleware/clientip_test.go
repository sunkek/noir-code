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
		// Normal chain: client appended by Traefik, then nginx appends Traefik's
		// private pod IP. Real client is the right-most public entry.
		{"client+proxy", "203.0.113.7, 10.42.0.3", "203.0.113.7", true},
		// Client forges an X-Forwarded-For; forged value sits left of the real
		// address Traefik observed and must be ignored.
		{"spoof prepended", "1.2.3.4, 203.0.113.7, 10.42.0.3", "203.0.113.7", true},
		{"spoof multiple", "9.9.9.9, 8.8.8.8, 203.0.113.7, 10.42.0.3", "203.0.113.7", true},
		// Only private hops (e.g. internal traffic) → no public client.
		{"all private", "10.0.0.1, 192.168.1.1", "", false},
		{"loopback+private", "127.0.0.1, 10.0.0.5", "", false},
		// IPv6 client.
		{"ipv6 client", "2606:4700::1111, fd00::1", "2606:4700::1111", true},
		// Malformed entries are skipped.
		{"garbage then public", "not-an-ip, 203.0.113.7, 10.0.0.1", "203.0.113.7", true},
		{"metadata not trusted as client", "169.254.169.254, 10.0.0.1", "", false},
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
