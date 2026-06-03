// Package urlfetch fetches a remote image by URL for the decode-by-URL feature.
// It is the single choke point for outbound egress and owns all the safety
// policy: SSRF protection (no private/loopback/link-local targets), a body-size
// cap, request timeouts, a redirect cap, and rate throttling. Keeping every
// outbound concern here means the domain just asks for bytes and never has to
// know it is talking to the open internet.
package urlfetch

import (
	"sync"
	"time"
)

// bucket is a lazy (refill-on-read) token bucket. Tokens accrue at rate per
// second up to capacity; one token is spent per allowed request.
type bucket struct {
	tokens float64
	last   time.Time
}

func (b *bucket) refill(now time.Time, rate, capacity float64) {
	b.tokens += now.Sub(b.last).Seconds() * rate
	if b.tokens > capacity {
		b.tokens = capacity
	}
	b.last = now
}

// throttle bounds outbound fetches two ways at once: a global bucket caps total
// egress (protecting us), and a per-host bucket caps requests to any single
// origin (protecting third-party targets from being hammered through us). A
// request is allowed only if BOTH buckets have a token, and only then are both
// spent — so a denied host never drains the global budget.
type throttle struct {
	mu     sync.Mutex
	global bucket
	hosts  map[string]*bucket

	globalRate, globalCap float64
	hostRate, hostCap     float64
}

func newThrottle(globalRate, globalCap, hostRate, hostCap float64) *throttle {
	now := time.Now()
	return &throttle{
		global:     bucket{tokens: globalCap, last: now},
		hosts:      make(map[string]*bucket),
		globalRate: globalRate,
		globalCap:  globalCap,
		hostRate:   hostRate,
		hostCap:    hostCap,
	}
}

// allow reports whether a fetch to host may proceed right now.
func (t *throttle) allow(host string) bool {
	now := time.Now()
	t.mu.Lock()
	defer t.mu.Unlock()

	hb, ok := t.hosts[host]
	if !ok {
		hb = &bucket{tokens: t.hostCap, last: now}
		t.hosts[host] = hb
	}
	t.global.refill(now, t.globalRate, t.globalCap)
	hb.refill(now, t.hostRate, t.hostCap)

	if t.global.tokens >= 1 && hb.tokens >= 1 {
		t.global.tokens--
		hb.tokens--
		return true
	}
	return false
}

// reap drops per-host buckets that have fully refilled (i.e. idle long enough to
// carry no state), bounding memory under a flood of distinct hosts.
func (t *throttle) reap() {
	now := time.Now()
	t.mu.Lock()
	defer t.mu.Unlock()
	for host, b := range t.hosts {
		b.refill(now, t.hostRate, t.hostCap)
		if b.tokens >= t.hostCap {
			delete(t.hosts, host)
		}
	}
}

func (t *throttle) janitor() {
	for range time.Tick(time.Minute) {
		t.reap()
	}
}
