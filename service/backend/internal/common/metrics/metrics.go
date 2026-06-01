// Package metrics holds the Prometheus collectors and a samsara MetricsObserver
// for the service. Collectors live on a dedicated registry exposed via Handler;
// instrumentation points call the small exported helpers so callers never touch
// prometheus types directly.
package metrics

import (
	"net/http"
	"strconv"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/collectors"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	reg = prometheus.NewRegistry()

	httpRequests = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "http_requests_total",
		Help: "Total HTTP requests by method, route, and status.",
	}, []string{"method", "route", "status"})

	httpDuration = prometheus.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "http_request_duration_seconds",
		Help:    "HTTP request latency by method and route.",
		Buckets: prometheus.DefBuckets,
	}, []string{"method", "route"})

	componentUp = prometheus.NewGaugeVec(prometheus.GaugeOpts{
		Name: "component_up",
		Help: "Whether a supervised component is currently running (1) or not (0).",
	}, []string{"component"})

	componentRestarts = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "component_restarts_total",
		Help: "Total restarts per supervised component.",
	}, []string{"component"})

	healthCheckDuration = prometheus.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "component_health_check_duration_seconds",
		Help:    "Health-check duration per supervised component.",
		Buckets: prometheus.DefBuckets,
	}, []string{"component"})
)

func init() {
	reg.MustRegister(
		httpRequests, httpDuration,
		componentUp, componentRestarts, healthCheckDuration,
		collectors.NewGoCollector(),
		collectors.NewProcessCollector(collectors.ProcessCollectorOpts{}),
	)
}

// Handler serves the metrics registry in Prometheus exposition format.
func Handler() http.Handler {
	return promhttp.HandlerFor(reg, promhttp.HandlerOpts{})
}

// ObserveHTTP records a completed HTTP request.
func ObserveHTTP(method, route string, status int, d time.Duration) {
	httpRequests.WithLabelValues(method, route, strconv.Itoa(status)).Inc()
	httpDuration.WithLabelValues(method, route).Observe(d.Seconds())
}

// Observer implements samsara.MetricsObserver (structurally), bridging
// supervisor telemetry into Prometheus.
type Observer struct{}

func NewObserver() Observer { return Observer{} }

func (Observer) ComponentStarted(component string, _ int) {
	componentUp.WithLabelValues(component).Set(1)
}
func (Observer) ComponentStopped(component string, _ error) {
	componentUp.WithLabelValues(component).Set(0)
}
func (Observer) ComponentRestarting(component string, _ error, _ int, _ time.Duration) {
	componentRestarts.WithLabelValues(component).Inc()
	componentUp.WithLabelValues(component).Set(0)
}
func (Observer) HealthCheckCompleted(component string, duration time.Duration, _ error) {
	healthCheckDuration.WithLabelValues(component).Observe(duration.Seconds())
}
