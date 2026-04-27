package jackettapi

import (
	"crypto/rand"
	"database/sql"
	"encoding/base64"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/db"
	"github.com/milos85vasic/qBitTorrent-go/internal/db/repos"
	"github.com/milos85vasic/qBitTorrent-go/internal/jackett"
)

// routerHarness wires real repos against a fresh file-backed SQLite DB.
// The Jackett client is left nil — handlers that don't reach Jackett still
// work; handlers that do reach it (HandleConfigureIndexer, etc.) are not
// exercised by these tests, which only verify routing behavior.
//
// triggerCalls counts invocations of the AutoconfigOnce closure — the
// fingerprint we use to confirm POST /autoconfig/run hit the trigger
// handler (not the list handler).
type routerHarness struct {
	mux          http.Handler
	deps         *Deps
	conn         *sql.DB
	triggerCalls *int64
	creds        *repos.Credentials
	idx          *repos.Indexers
	cat          *repos.Catalog
	runs         *repos.Runs
	overrides    *repos.Overrides
	envPath      string
}

func newRouterHarness(t *testing.T) *routerHarness {
	t.Helper()
	dir := t.TempDir()
	conn, err := db.Open(filepath.Join(dir, "router.db"))
	if err != nil {
		t.Fatalf("db.Open: %v", err)
	}
	t.Cleanup(func() { _ = conn.Close() })
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		t.Fatalf("rand: %v", err)
	}

	credsRepo := repos.NewCredentials(conn, key)
	idxRepo := repos.NewIndexers(conn)
	catRepo := repos.NewCatalog(conn)
	runsRepo := repos.NewRuns(conn)
	overridesRepo := repos.NewOverrides(conn)

	envPath := filepath.Join(dir, ".env")
	if err := os.WriteFile(envPath, []byte(""), 0o600); err != nil {
		t.Fatalf("seed env: %v", err)
	}

	var trigger int64
	deps := &Deps{
		Credentials: &CredentialsDeps{
			Repo:              credsRepo,
			Indexers:          idxRepo,
			Jackett:           nil,
			EnvPath:           envPath,
			AutoconfigTrigger: func() {},
		},
		Indexers: &IndexersDeps{
			Indexers: idxRepo, Creds: credsRepo, Catalog: catRepo, Jackett: nil,
		},
		Catalog: &CatalogDeps{Catalog: catRepo, Jackett: nil},
		Runs: &RunsDeps{
			Repo: runsRepo,
			AutoconfigOnce: func() jackett.AutoconfigResult {
				atomic.AddInt64(&trigger, 1)
				return jackett.AutoconfigResult{
					RanAt:                 time.Now().UTC(),
					DiscoveredCredentials: []string{},
					MatchedIndexers:       map[string]string{},
					ConfiguredNow:         []string{},
					AlreadyPresent:        []string{},
					SkippedNoMatch:        []string{},
					SkippedAmbiguous:      []jackett.AmbiguousMatch{},
					Errors:                []string{},
				}
			},
		},
		Overrides: &OverridesDeps{Repo: overridesRepo},
		Health: &HealthDeps{
			DB: conn, Jackett: nil, Version: "test", StartTime: time.Now().UTC(),
		},
	}
	return &routerHarness{
		mux:          NewMux(deps),
		deps:         deps,
		conn:         conn,
		triggerCalls: &trigger,
		creds:        credsRepo,
		idx:          idxRepo,
		cat:          catRepo,
		runs:         runsRepo,
		overrides:    overridesRepo,
		envPath:      envPath,
	}
}

// adminAuthHeader is "Basic <base64(admin:admin)>" — used for the small
// number of router tests that need to traverse WithAuth.
var adminAuthHeader = "Basic " + base64.StdEncoding.EncodeToString([]byte("admin:admin"))

func TestNewMuxHealthzReachable(t *testing.T) {
	h := newRouterHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("/healthz: want 200, got %d body=%s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"db_ok":true`) {
		t.Fatalf("expected db_ok=true in healthz body, got %s", rec.Body.String())
	}
}

func TestNewMuxRoutesGETCredentials(t *testing.T) {
	h := newRouterHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/v1/jackett/credentials", nil)
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("GET /credentials: want 200, got %d body=%s", rec.Code, rec.Body.String())
	}
	if got := strings.TrimSpace(rec.Body.String()); got != "[]" {
		t.Fatalf("GET /credentials: want [], got %q", got)
	}
}

func TestNewMuxRoutesPOSTCredentialsRequiresAuth(t *testing.T) {
	h := newRouterHarness(t)
	// Without auth → 401 from WithAuth (proves auth is wired).
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/api/v1/jackett/credentials",
		strings.NewReader(`{}`))
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("POST /credentials no-auth: want 401, got %d", rec.Code)
	}

	// With admin/admin → reaches handler, fails on missing name → 400.
	rec = httptest.NewRecorder()
	req = httptest.NewRequest(http.MethodPost, "/api/v1/jackett/credentials",
		strings.NewReader(`{}`))
	req.Header.Set("Authorization", adminAuthHeader)
	req.Header.Set("Content-Type", "application/json")
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("POST /credentials with auth empty body: want 400, got %d body=%s",
			rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), "missing_name") {
		t.Fatalf("expected missing_name error, got %s", rec.Body.String())
	}
}

func TestNewMuxRoutesDELETECredentialsByName(t *testing.T) {
	h := newRouterHarness(t)
	if err := h.creds.Upsert("RUTRACKER", "userpass",
		strPtrRT("u"), strPtrRT("p"), nil); err != nil {
		t.Fatalf("seed: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodDelete,
		"/api/v1/jackett/credentials/RUTRACKER", nil)
	req.Header.Set("Authorization", adminAuthHeader)
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusNoContent {
		t.Fatalf("DELETE /credentials/RUTRACKER: want 204, got %d body=%s",
			rec.Code, rec.Body.String())
	}
}

// TestNewMuxAutoconfigRunVsRunsDistinguished is the critical anti-collision
// test. The three URL prefixes share "/autoconfig/run" but stdlib ServeMux
// resolves them correctly:
//
//   - POST /autoconfig/run     → HandleTriggerRun (counter increments)
//   - GET  /autoconfig/runs    → HandleListRuns   (counter unchanged)
//   - GET  /autoconfig/runs/1  → HandleGetRun     (counter unchanged, 404 for unknown id)
func TestNewMuxAutoconfigRunVsRunsDistinguished(t *testing.T) {
	h := newRouterHarness(t)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost,
		"/api/v1/jackett/autoconfig/run", nil)
	req.Header.Set("Authorization", adminAuthHeader)
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("POST /autoconfig/run: want 200, got %d body=%s",
			rec.Code, rec.Body.String())
	}
	if got := atomic.LoadInt64(h.triggerCalls); got != 1 {
		t.Fatalf("trigger should run once, got %d", got)
	}

	rec = httptest.NewRecorder()
	req = httptest.NewRequest(http.MethodGet,
		"/api/v1/jackett/autoconfig/runs", nil)
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("GET /autoconfig/runs: want 200, got %d body=%s",
			rec.Code, rec.Body.String())
	}
	if got := atomic.LoadInt64(h.triggerCalls); got != 1 {
		t.Fatalf("list should NOT trigger autoconfig, counter=%d", got)
	}

	rec = httptest.NewRecorder()
	req = httptest.NewRequest(http.MethodGet,
		"/api/v1/jackett/autoconfig/runs/9999", nil)
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusNotFound {
		t.Fatalf("GET /autoconfig/runs/9999: want 404, got %d body=%s",
			rec.Code, rec.Body.String())
	}
	if got := atomic.LoadInt64(h.triggerCalls); got != 1 {
		t.Fatalf("get-by-id should NOT trigger autoconfig, counter=%d", got)
	}
}

// TestNewMuxRoutesIndexerTestEndpoint verifies that POST /indexers/{id}/test
// dispatches to HandleTestIndexer rather than HandleConfigureIndexer. With
// an unreachable Jackett client, HandleTestIndexer returns status:"unreachable";
// HandleConfigureIndexer would 400 on missing credential_name. The status
// field in the response body uniquely identifies which handler ran.
func TestNewMuxRoutesIndexerTestEndpoint(t *testing.T) {
	h := newRouterHarness(t)
	// Install an unreachable Jackett client so HandleTestIndexer returns
	// "unreachable" without panicking on nil pointer.
	stubClient := jackett.NewClient("http://127.0.0.1:1", "deadbeef")
	h.deps.Indexers.Jackett = stubClient
	h.mux = NewMux(h.deps)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost,
		"/api/v1/jackett/indexers/some-id/test", nil)
	req.Header.Set("Authorization", adminAuthHeader)
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("POST /indexers/some-id/test: want 200, got %d body=%s",
			rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"status"`) {
		t.Fatalf("expected JSON test result, got %s", rec.Body.String())
	}
	if strings.Contains(rec.Body.String(), "missing_credential_name") {
		t.Fatalf("dispatched to configure handler, not test handler: %s",
			rec.Body.String())
	}
}

func TestNewMuxRoutesCatalogRefreshIsPOST(t *testing.T) {
	h := newRouterHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet,
		"/api/v1/jackett/catalog/refresh", nil)
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("GET /catalog/refresh: want 405, got %d", rec.Code)
	}
}

func TestNewMuxRoutesOverridesByEnvName(t *testing.T) {
	h := newRouterHarness(t)
	if err := h.overrides.Upsert("FOO", "indexer-x"); err != nil {
		t.Fatalf("seed: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodDelete,
		"/api/v1/jackett/overrides/FOO", nil)
	req.Header.Set("Authorization", adminAuthHeader)
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusNoContent {
		t.Fatalf("DELETE /overrides/FOO: want 204, got %d body=%s",
			rec.Code, rec.Body.String())
	}
}

// TestNewMuxAuthEnforced confirms that WithAuth wraps the registered mux —
// any non-GET method without credentials gets 401.
func TestNewMuxAuthEnforced(t *testing.T) {
	h := newRouterHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost,
		"/api/v1/jackett/overrides", strings.NewReader(`{}`))
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("POST /overrides without auth: want 401, got %d", rec.Code)
	}
}

func TestNewMuxRoutesUnknownPath404(t *testing.T) {
	h := newRouterHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/no/such/path", nil)
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusNotFound {
		t.Fatalf("unknown path: want 404, got %d", rec.Code)
	}
}

// strPtrRT is a string-pointer helper for router tests. Named distinctly
// from strPtr in credentials_test.go to make the call sites easy to grep
// while keeping the helper local to this file's harness.
func strPtrRT(s string) *string { return &s }
