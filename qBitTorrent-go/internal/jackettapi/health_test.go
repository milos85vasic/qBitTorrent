package jackettapi

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"sync/atomic"
	"testing"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/db"
	"github.com/milos85vasic/qBitTorrent-go/internal/jackett"
)

// healthHarness wires a real DB + a stub Jackett HTTP server so we can
// drive both subsystems independently. The atomic counter is the
// CONST-XII falsification guard for TestHealthAllOK: a hardcoded
// `JackettOk: true` would never increment it.
type healthHarness struct {
	deps         *HealthDeps
	server       *httptest.Server
	catalogCalls int32
	catalogFail  bool
}

func newHealthHarness(t *testing.T) *healthHarness {
	t.Helper()
	dir := t.TempDir()
	conn, err := db.Open(filepath.Join(dir, "t.db"))
	if err != nil {
		t.Fatalf("db.Open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	h := &healthHarness{}
	h.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/UI/Dashboard":
			w.WriteHeader(302)
		case "/api/v2.0/indexers":
			atomic.AddInt32(&h.catalogCalls, 1)
			if h.catalogFail {
				w.WriteHeader(500)
				return
			}
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`[]`))
		default:
			w.WriteHeader(404)
		}
	}))
	h.deps = &HealthDeps{
		DB:        conn,
		Jackett:   jackett.NewClient(h.server.URL, "k"),
		Version:   "test-1.0",
		StartTime: time.Now().UTC(),
	}
	t.Cleanup(func() {
		h.server.Close()
		_ = conn.Close()
	})
	return h
}

func TestHealthAllOK(t *testing.T) {
	h := newHealthHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/healthz", nil)
	h.deps.HandleHealth(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	var got healthDTO
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v body=%s", err, rec.Body.String())
	}
	if got.Status != "ok" {
		t.Fatalf("status: %s", got.Status)
	}
	if !got.DBOk || !got.JackettOk {
		t.Fatalf("subsystems: %+v", got)
	}
	if got.Version != "test-1.0" {
		t.Fatalf("version: %s", got.Version)
	}
	if got.UptimeS < 0 {
		t.Fatalf("uptime negative: %d", got.UptimeS)
	}
	// CONST-XII: confirm Jackett was actually probed. A handler that
	// hardcoded JackettOk:true without dialing the upstream would leave
	// this counter at zero.
	if atomic.LoadInt32(&h.catalogCalls) == 0 {
		t.Fatalf("Jackett /api/v2.0/indexers not hit: %d", h.catalogCalls)
	}
}

func TestHealthJackettDownDegraded(t *testing.T) {
	h := newHealthHarness(t)
	h.catalogFail = true
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/healthz", nil)
	h.deps.HandleHealth(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d", rec.Code)
	}
	var got healthDTO
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if got.Status != "degraded" {
		t.Fatalf("status: %s", got.Status)
	}
	if !got.DBOk {
		t.Fatalf("db should be ok: %+v", got)
	}
	if got.JackettOk {
		t.Fatalf("jackett should be down: %+v", got)
	}
}

func TestHealthDBClosedUnhealthy(t *testing.T) {
	h := newHealthHarness(t)
	_ = h.deps.DB.Close() // simulate DB failure
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/healthz", nil)
	h.deps.HandleHealth(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d", rec.Code)
	}
	var got healthDTO
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if got.Status != "unhealthy" {
		t.Fatalf("status: %s", got.Status)
	}
	if got.DBOk {
		t.Fatalf("db should be down: %+v", got)
	}
}

func TestHealthVersionAndUptimeSurfaced(t *testing.T) {
	h := newHealthHarness(t)
	h.deps.Version = "v1.2.3"
	h.deps.StartTime = time.Now().UTC().Add(-90 * time.Second)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/healthz", nil)
	h.deps.HandleHealth(rec, req)
	var got healthDTO
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if got.Version != "v1.2.3" {
		t.Fatalf("version: %s", got.Version)
	}
	// CONST-XII falsification: a handler returning hardcoded UptimeS:0
	// would fail this range check; one returning the wrong sign would
	// also fail.
	if got.UptimeS < 89 || got.UptimeS > 95 {
		t.Fatalf("uptime ~90s expected, got %d", got.UptimeS)
	}
}

func TestHealthBothNilSafe(t *testing.T) {
	h := newHealthHarness(t)
	h.deps.DB = nil
	h.deps.Jackett = nil
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/healthz", nil)
	h.deps.HandleHealth(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d", rec.Code)
	}
	var got healthDTO
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if got.DBOk || got.JackettOk {
		t.Fatalf("nil deps should report false: %+v", got)
	}
	if got.Status != "unhealthy" {
		t.Fatalf("status: %s", got.Status)
	}
}
