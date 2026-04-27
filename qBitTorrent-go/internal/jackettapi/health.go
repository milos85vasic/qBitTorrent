package jackettapi

import (
	"context"
	"database/sql"
	"net/http"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/jackett"
)

// HealthDeps wires the readiness checkers for the /healthz endpoint.
//
// Version is the build version (set at link-time or at main.go init).
// StartTime is captured at process start so uptime can be reported.
//
// The handler always returns HTTP 200 even when a subsystem is down —
// monitors should watch the body fields. Flapping HTTP status is
// noisier than a stable JSON change.
type HealthDeps struct {
	DB        *sql.DB
	Jackett   *jackett.Client
	Version   string
	StartTime time.Time
}

// healthDTO is the spec §8.6 response shape.
type healthDTO struct {
	Status    string `json:"status"`
	DBOk      bool   `json:"db_ok"`
	JackettOk bool   `json:"jackett_ok"`
	Version   string `json:"version"`
	UptimeS   int64  `json:"uptime_s"`
}

// HandleHealth handles GET /healthz.
//
// DB readiness: PingContext with a 2s deadline. Any error → DBOk=false.
//
// Jackett readiness: GetCatalog with the client's default timeout. Any
// non-error response (including an empty list) is treated as healthy.
// NOTE: GetCatalog is the most lightweight readiness signal Jackett's
// public API offers today. If a dedicated low-overhead Ping endpoint
// is added upstream, this is the call to swap.
//
// Status mapping:
//   - both up        → "ok"
//   - DB up only     → "degraded" (Jackett is fixable without restart)
//   - DB down        → "unhealthy" (nothing else works without it)
func (d *HealthDeps) HandleHealth(w http.ResponseWriter, r *http.Request) {
	out := healthDTO{
		Version: d.Version,
		UptimeS: int64(time.Since(d.StartTime).Seconds()),
	}
	if d.DB != nil {
		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		out.DBOk = d.DB.PingContext(ctx) == nil
		cancel()
	}
	if d.Jackett != nil {
		_, err := d.Jackett.GetCatalog()
		out.JackettOk = err == nil
	}
	switch {
	case out.DBOk && out.JackettOk:
		out.Status = "ok"
	case out.DBOk:
		out.Status = "degraded"
	default:
		out.Status = "unhealthy"
	}
	writeJSON(w, http.StatusOK, out)
}
