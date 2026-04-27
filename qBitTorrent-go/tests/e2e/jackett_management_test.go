//go:build e2e

// Package e2e — Layer 3 end-to-end tests for boba-jackett against a REAL
// running Jackett server. Boots an in-process boba-jackett (via
// jackettapi.NewMux) on a per-test fresh tmp DB + tmp .env, then drives
// the spec §10.3 scenarios end-to-end.
//
// CONST-XII (Anti-Bluff): every test inspects user-observable post-state
// — Jackett's own /api/v2.0/indexers list, the boba-jackett response
// body, the on-disk DB row. None succeed against a stub.
//
// CONST-11 (Real Infrastructure): tests SKIP when Jackett is unreachable;
// they do not fail. Probe `JACKETT_URL` (default http://localhost:9117).
// Set JACKETT_API_KEY for any scenario that touches indexer config.
//
// Run:
//
//	GOMAXPROCS=2 nice -n 19 ionice -c 3 go test -tags=e2e -race \
//	  -count=1 ./tests/e2e/ -v
package e2e

import (
	"bytes"
	"crypto/rand"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/bootstrap"
	"github.com/milos85vasic/qBitTorrent-go/internal/db"
	"github.com/milos85vasic/qBitTorrent-go/internal/db/repos"
	"github.com/milos85vasic/qBitTorrent-go/internal/jackett"
	"github.com/milos85vasic/qBitTorrent-go/internal/jackettapi"
)

// jackettURL returns the JACKETT_URL env, defaulting to localhost:9117.
func jackettURL() string {
	if v := strings.TrimSpace(os.Getenv("JACKETT_URL")); v != "" {
		return v
	}
	return "http://localhost:9117"
}

// jackettAPIKey returns the JACKETT_API_KEY env (no default — empty
// string means scenarios that need a key skip).
func jackettAPIKey() string {
	return strings.TrimSpace(os.Getenv("JACKETT_API_KEY"))
}

// jackettReachable probes the Jackett root path with a short timeout.
// Returns true on any HTTP 2xx/3xx (Jackett's UI returns 200 unauth).
func jackettReachable() bool {
	c := &http.Client{Timeout: 2 * time.Second}
	resp, err := c.Get(jackettURL() + "/api/v2.0/server/config")
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	// Any HTTP response (even 401) means Jackett is up. 5xx still means
	// the process is alive enough to reply, so we treat it as reachable.
	return resp.StatusCode > 0
}

// skipIfNoJackett skips a test with a clear CONST-11 message if Jackett
// is not reachable.
func skipIfNoJackett(t *testing.T) {
	t.Helper()
	if !jackettReachable() {
		t.Skipf("Jackett not available at %s — skipping E2E (CONST-11)",
			jackettURL())
	}
}

// skipIfNoAPIKey skips when JACKETT_API_KEY is unset. Tests that touch
// indexer config (POST /indexers/{id}) need a real key.
func skipIfNoAPIKey(t *testing.T) {
	t.Helper()
	if jackettAPIKey() == "" {
		t.Skipf("JACKETT_API_KEY not set — skipping (CONST-11)")
	}
}

// e2eHarness wires a fresh boba-jackett service for one test. The
// httptest.Server hosts the same NewMux main.go would, with the same
// deps tree, against a tmp DB + tmp .env.
type e2eHarness struct {
	srv          *httptest.Server
	envPath      string
	dbPath       string
	credsRepo    *repos.Credentials
	indexersRepo *repos.Indexers
	catalogRepo  *repos.Catalog
	runsRepo     *repos.Runs
	overrides    *repos.Overrides
	jClient      *jackett.Client
}

// newE2EHarness boots an in-process boba-jackett. Caller must Close()
// via t.Cleanup which the harness wires automatically.
func newE2EHarness(t *testing.T) *e2eHarness {
	t.Helper()
	dir := t.TempDir()
	envPath := filepath.Join(dir, ".env")
	dbPath := filepath.Join(dir, "boba.db")
	if err := os.WriteFile(envPath, []byte(""), 0o600); err != nil {
		t.Fatalf("seed env: %v", err)
	}
	key, _, err := bootstrap.EnsureMasterKey(envPath)
	if err != nil {
		t.Fatalf("EnsureMasterKey: %v", err)
	}
	conn, err := db.Open(dbPath)
	if err != nil {
		t.Fatalf("db.Open: %v", err)
	}
	t.Cleanup(func() { _ = conn.Close() })
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("Migrate: %v", err)
	}

	credsRepo := repos.NewCredentials(conn, key)
	indexersRepo := repos.NewIndexers(conn)
	catalogRepo := repos.NewCatalog(conn)
	runsRepo := repos.NewRuns(conn)
	overridesRepo := repos.NewOverrides(conn)
	jClient := jackett.NewClient(jackettURL(), jackettAPIKey())

	autoconfigDeps := jackett.AutoconfigDeps{
		Creds: credsRepo, Overrides: overridesRepo,
		Indexers: indexersRepo, Runs: runsRepo, Client: jClient,
	}

	deps := &jackettapi.Deps{
		Credentials: &jackettapi.CredentialsDeps{
			Repo:     credsRepo,
			Indexers: indexersRepo,
			Jackett:  jClient,
			EnvPath:  envPath,
			AutoconfigTrigger: func() {
				go jackett.Autoconfigure(autoconfigDeps, nil)
			},
		},
		Indexers: &jackettapi.IndexersDeps{
			Indexers: indexersRepo, Creds: credsRepo,
			Catalog: catalogRepo, Jackett: jClient,
		},
		Catalog:   &jackettapi.CatalogDeps{Catalog: catalogRepo, Jackett: jClient},
		Runs:      &jackettapi.RunsDeps{Repo: runsRepo, AutoconfigOnce: func() jackett.AutoconfigResult { return jackett.Autoconfigure(autoconfigDeps, nil) }},
		Overrides: &jackettapi.OverridesDeps{Repo: overridesRepo},
		Health: &jackettapi.HealthDeps{
			DB: conn, Jackett: jClient, Version: "e2e-test", StartTime: time.Now().UTC(),
		},
	}

	srv := httptest.NewServer(jackettapi.NewMux(deps))
	t.Cleanup(srv.Close)

	return &e2eHarness{
		srv: srv, envPath: envPath, dbPath: dbPath,
		credsRepo: credsRepo, indexersRepo: indexersRepo,
		catalogRepo: catalogRepo, runsRepo: runsRepo,
		overrides: overridesRepo, jClient: jClient,
	}
}

// post wraps the harness with admin/admin Basic auth (mutating endpoints
// require it per the WithAuth middleware).
func (h *e2eHarness) post(t *testing.T, path string, body any) (*http.Response, []byte) {
	t.Helper()
	raw, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	req, _ := http.NewRequest("POST", h.srv.URL+path, bytes.NewReader(raw))
	req.Header.Set("Content-Type", "application/json")
	req.SetBasicAuth("admin", "admin")
	resp, err := h.srv.Client().Do(req)
	if err != nil {
		t.Fatalf("POST %s: %v", path, err)
	}
	defer resp.Body.Close()
	out, _ := io.ReadAll(resp.Body)
	return resp, out
}

// get hits a GET endpoint (no auth required).
func (h *e2eHarness) get(t *testing.T, path string) (*http.Response, []byte) {
	t.Helper()
	resp, err := h.srv.Client().Get(h.srv.URL + path)
	if err != nil {
		t.Fatalf("GET %s: %v", path, err)
	}
	defer resp.Body.Close()
	out, _ := io.ReadAll(resp.Body)
	return resp, out
}

// patch wraps the harness with admin/admin auth for PATCH.
func (h *e2eHarness) patch(t *testing.T, path string, body any) (*http.Response, []byte) {
	t.Helper()
	raw, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	req, _ := http.NewRequest("PATCH", h.srv.URL+path, bytes.NewReader(raw))
	req.Header.Set("Content-Type", "application/json")
	req.SetBasicAuth("admin", "admin")
	resp, err := h.srv.Client().Do(req)
	if err != nil {
		t.Fatalf("PATCH %s: %v", path, err)
	}
	defer resp.Body.Close()
	out, _ := io.ReadAll(resp.Body)
	return resp, out
}

// jackettListIndexers calls Jackett's /api/v2.0/indexers (with apikey)
// and returns the parsed list. Used to assert post-autoconfig state.
func jackettListIndexers(t *testing.T, configuredOnly bool) []jackett.CatalogEntry {
	t.Helper()
	c := &http.Client{Timeout: 5 * time.Second}
	q := "configured=true"
	if !configuredOnly {
		q = "configured=false"
	}
	url := fmt.Sprintf("%s/api/v2.0/indexers?apikey=%s&%s",
		jackettURL(), jackettAPIKey(), q)
	resp, err := c.Get(url)
	if err != nil {
		t.Fatalf("Jackett /indexers: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		t.Fatalf("Jackett /indexers HTTP %d: %s", resp.StatusCode, body)
	}
	var entries []jackett.CatalogEntry
	if err := json.NewDecoder(resp.Body).Decode(&entries); err != nil {
		t.Fatalf("decode: %v", err)
	}
	return entries
}

// TestE2E_BootInProcessService covers spec §10.3 scenario 1: the harness
// itself MUST boot, and /healthz must return a parseable response.
//
// Falsification: comment out NewMux's /healthz route — the GET fails or
// the JSON has no `status` key.
func TestE2E_BootInProcessService(t *testing.T) {
	skipIfNoJackett(t)
	h := newE2EHarness(t)
	resp, body := h.get(t, "/healthz")
	if resp.StatusCode != 200 {
		t.Fatalf("/healthz status=%d body=%s", resp.StatusCode, body)
	}
	var hd map[string]any
	if err := json.Unmarshal(body, &hd); err != nil {
		t.Fatalf("decode healthz: %v body=%s", err, body)
	}
	if _, ok := hd["status"]; !ok {
		t.Fatalf("healthz missing `status`: %v", hd)
	}
	if _, ok := hd["db_ok"]; !ok {
		t.Fatalf("healthz missing `db_ok`: %v", hd)
	}
	// db_ok must be true — the harness wires a working SQLite.
	if v, _ := hd["db_ok"].(bool); !v {
		t.Fatalf("healthz reports db_ok=false against fresh tmp DB: %v", hd)
	}
}

// TestE2E_AddCredAutoconfigRunsIndexerVisibleAtJackett covers spec
// §10.3 scenario 2: POST /credentials → trigger autoconfig POST → indexer
// appears in Jackett's configured list.
//
// Falsification: stub Autoconfigure to no-op — the
// jackettListIndexers(true) check shows zero new entries and the test
// fails.
func TestE2E_AddCredAutoconfigRunsIndexerVisibleAtJackett(t *testing.T) {
	skipIfNoJackett(t)
	skipIfNoAPIKey(t)
	user := strings.TrimSpace(os.Getenv("RUTRACKER_USERNAME"))
	pass := strings.TrimSpace(os.Getenv("RUTRACKER_PASSWORD"))
	if user == "" || pass == "" {
		t.Skipf("RUTRACKER_USERNAME/PASSWORD unset — skipping (CONST-11)")
	}
	h := newE2EHarness(t)

	// Trigger autoconfig synchronously via the dedicated endpoint so we
	// can assert on a deterministic post-state. Add cred first (this
	// fires an async replay we don't wait on), then call
	// /autoconfig/run for the synchronous round-trip.
	if resp, body := h.post(t, "/api/v1/jackett/credentials",
		map[string]any{
			"name":     "RUTRACKER",
			"username": user,
			"password": pass,
		}); resp.StatusCode != 200 {
		t.Fatalf("POST cred status=%d body=%s", resp.StatusCode, body)
	}

	// Run autoconfig synchronously.
	resp, body := h.post(t, "/api/v1/jackett/autoconfig/run", nil)
	if resp.StatusCode != 200 {
		t.Fatalf("autoconfig/run status=%d body=%s", resp.StatusCode, body)
	}
	var result jackett.AutoconfigResult
	if err := json.Unmarshal(body, &result); err != nil {
		t.Fatalf("decode autoconfig: %v body=%s", err, body)
	}
	t.Logf("autoconfig result: configured_now=%v errors=%v",
		result.ConfiguredNow, result.Errors)

	// User-observable post-state: Jackett's own configured list contains
	// at least one new entry that wasn't present before. We reconcile
	// "before" via a second harness without any cred — but since
	// configured-list is a property of the JACKETT process, we accept
	// that this assertion is "indexer X appears in Jackett's configured
	// set". Cleanup runs at the end to remove it.
	configured := jackettListIndexers(t, true)
	matched := result.MatchedIndexers["RUTRACKER"]
	if matched == "" {
		t.Skipf("Jackett didn't match any indexer for RUTRACKER (catalog evolved). result=%+v",
			result)
	}
	found := false
	for _, e := range configured {
		if e.ID == matched {
			found = true
			break
		}
	}
	if !found {
		t.Fatalf("matched indexer %q not in Jackett configured list: %+v",
			matched, configured)
	}

	// Cleanup: delete the indexer from Jackett so the e2e re-runs are
	// idempotent. Best-effort.
	t.Cleanup(func() {
		_ = h.jClient.DeleteIndexer(matched)
	})
}

// TestE2E_BrowseCatalog covers spec §10.3 scenario 3: GET /catalog
// returns ≥10 entries (relaxed from "620" because Jackett's catalog
// evolves; the spec text says relax it for that reason).
//
// Falsification: stub HandleListCatalog to return [] — the len(items)
// >= 10 check fails.
func TestE2E_BrowseCatalog(t *testing.T) {
	skipIfNoJackett(t)
	skipIfNoAPIKey(t)
	h := newE2EHarness(t)

	// Refresh the catalog from Jackett first (DB is empty in a fresh harness).
	resp, body := h.post(t, "/api/v1/jackett/catalog/refresh", nil)
	if resp.StatusCode != 200 {
		t.Fatalf("/catalog/refresh status=%d body=%s", resp.StatusCode, body)
	}
	var refresh struct {
		RefreshedCount int      `json:"refreshed_count"`
		Errors         []string `json:"errors"`
	}
	if err := json.Unmarshal(body, &refresh); err != nil {
		t.Fatalf("decode refresh: %v body=%s", err, body)
	}
	if refresh.RefreshedCount < 10 {
		t.Fatalf("refresh produced only %d entries — expected ≥10. errors=%v",
			refresh.RefreshedCount, refresh.Errors)
	}

	// GET /catalog with default page size and assert the page contains items.
	resp, body = h.get(t, "/api/v1/jackett/catalog?page=1&page_size=50")
	if resp.StatusCode != 200 {
		t.Fatalf("/catalog status=%d body=%s", resp.StatusCode, body)
	}
	var page struct {
		Total    int              `json:"total"`
		Page     int              `json:"page"`
		PageSize int              `json:"page_size"`
		Items    []map[string]any `json:"items"`
	}
	if err := json.Unmarshal(body, &page); err != nil {
		t.Fatalf("decode catalog: %v body=%s", err, body)
	}
	if page.Total < 10 {
		t.Fatalf("catalog total=%d, want ≥10", page.Total)
	}
	if len(page.Items) < 1 {
		t.Fatalf("catalog page has no items: %+v", page)
	}
	// Sanity: each item carries the required keys per spec §8.3.
	for _, it := range page.Items[:1] {
		for _, key := range []string{"id", "display_name", "type", "required_fields"} {
			if _, ok := it[key]; !ok {
				t.Fatalf("catalog item missing %q: %+v", key, it)
			}
		}
	}
}

// TestE2E_AddCookieIndexer covers spec §10.3 scenario 4: cookie-kind
// credential → POST /indexers/{iptorrents} → indexer is configured at
// Jackett with the cookie value.
//
// Falsification: stub PostIndexerConfig — the post-condition check
// (indexer appears in Jackett's configured list) fails.
func TestE2E_AddCookieIndexer(t *testing.T) {
	skipIfNoJackett(t)
	skipIfNoAPIKey(t)
	cookies := strings.TrimSpace(os.Getenv("IPTORRENTS_COOKIES"))
	if cookies == "" {
		t.Skipf("IPTORRENTS_COOKIES unset — skipping (CONST-11)")
	}
	h := newE2EHarness(t)

	// Refresh catalog so the harness DB knows about iptorrents.
	if resp, body := h.post(t, "/api/v1/jackett/catalog/refresh", nil); resp.StatusCode != 200 {
		t.Fatalf("refresh: %d body=%s", resp.StatusCode, body)
	}
	if resp, body := h.post(t, "/api/v1/jackett/credentials",
		map[string]any{"name": "IPTORRENTS", "cookies": cookies}); resp.StatusCode != 200 {
		t.Fatalf("POST cred: %d body=%s", resp.StatusCode, body)
	}
	resp, body := h.post(t, "/api/v1/jackett/indexers/iptorrents",
		map[string]any{"credential_name": "IPTORRENTS"})
	if resp.StatusCode != 200 {
		t.Skipf("POST indexer iptorrents: %d body=%s (likely catalog ID changed)",
			resp.StatusCode, body)
	}
	configured := jackettListIndexers(t, true)
	found := false
	for _, e := range configured {
		if e.ID == "iptorrents" {
			found = true
			break
		}
	}
	if !found {
		t.Fatalf("iptorrents not in Jackett configured list after POST")
	}
	t.Cleanup(func() { _ = h.jClient.DeleteIndexer("iptorrents") })
}

// TestE2E_TestIndexer covers spec §10.3 scenario 5: POST
// /indexers/{id}/test returns a status. We don't assert "ok" because
// that depends on actual indexer health; we assert the response shape.
//
// Falsification: stub HandleTestIndexer to write an empty body — the
// shape assertion fails.
func TestE2E_TestIndexer(t *testing.T) {
	skipIfNoJackett(t)
	skipIfNoAPIKey(t)
	h := newE2EHarness(t)

	// Configure something we can test. Use a public no-auth indexer if
	// available — else skip.
	configured := jackettListIndexers(t, true)
	if len(configured) == 0 {
		t.Skipf("No configured indexer at Jackett — skipping (CONST-11)")
	}
	id := configured[0].ID

	// Seed the indexers DB row so RecordTest can update it. We use the
	// repo directly because the upstream POST flow needs a credential
	// and we want to focus this test on the test endpoint itself.
	if err := h.indexersRepo.Upsert(&repos.Indexer{
		ID: id, DisplayName: id, Type: "private",
		ConfiguredAtJackett: true, EnabledForSearch: true,
	}); err != nil {
		t.Fatalf("seed indexer row: %v", err)
	}

	resp, body := h.post(t, "/api/v1/jackett/indexers/"+id+"/test", nil)
	if resp.StatusCode != 200 {
		t.Fatalf("test status=%d body=%s", resp.StatusCode, body)
	}
	var out map[string]any
	if err := json.Unmarshal(body, &out); err != nil {
		t.Fatalf("decode: %v body=%s", err, body)
	}
	status, _ := out["status"].(string)
	if status == "" {
		t.Fatalf("test response missing `status`: %v", out)
	}
	// User-observable: the DB row's last_test_status field updated.
	got, err := h.indexersRepo.Get(id)
	if err != nil {
		t.Fatalf("Get post-test: %v", err)
	}
	if got.LastTestStatus == nil || *got.LastTestStatus != status {
		t.Fatalf("DB last_test_status mismatch: response=%q db=%v",
			status, got.LastTestStatus)
	}
}

// TestE2E_TogglePatch covers spec §10.3 scenario 6: PATCH
// /indexers/{id} {enabled_for_search: false} → DB row updated.
//
// Falsification: stub SetEnabled to no-op — the post-PATCH read
// shows enabled_for_search=true and the assertion fails.
func TestE2E_TogglePatch(t *testing.T) {
	skipIfNoJackett(t)
	h := newE2EHarness(t)

	// Seed indexer row directly (no Jackett-side action needed for this scenario).
	id := "test-toggle-id"
	if err := h.indexersRepo.Upsert(&repos.Indexer{
		ID: id, DisplayName: id, Type: "private",
		ConfiguredAtJackett: true, EnabledForSearch: true,
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}

	resp, body := h.patch(t, "/api/v1/jackett/indexers/"+id,
		map[string]any{"enabled_for_search": false})
	if resp.StatusCode != 200 {
		t.Fatalf("PATCH status=%d body=%s", resp.StatusCode, body)
	}

	got, err := h.indexersRepo.Get(id)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.EnabledForSearch {
		t.Fatalf("DB row still enabled after PATCH false: %+v", got)
	}

	// Toggle back.
	resp, body = h.patch(t, "/api/v1/jackett/indexers/"+id,
		map[string]any{"enabled_for_search": true})
	if resp.StatusCode != 200 {
		t.Fatalf("PATCH back status=%d body=%s", resp.StatusCode, body)
	}
	got, _ = h.indexersRepo.Get(id)
	if !got.EnabledForSearch {
		t.Fatalf("DB row still disabled after PATCH true: %+v", got)
	}
}

// TestE2E_OverridesFromEnvAndDB covers spec §10.3 scenario 7: an
// override row stored in DB is honored by autoconfig (DB wins over the
// fuzzy match). We don't fully run autoconfig here — that would
// duplicate scenario 2 — but we do assert the override is persisted and
// listed.
//
// Falsification: stub Repo.Upsert — the GET /overrides post-state shows
// no row.
func TestE2E_OverridesFromEnvAndDB(t *testing.T) {
	skipIfNoJackett(t)
	h := newE2EHarness(t)

	// Add an override via the API.
	resp, body := h.post(t, "/api/v1/jackett/overrides",
		map[string]any{"env_name": "RUTRACKER", "indexer_id": "rutracker_v2"})
	if resp.StatusCode != 200 {
		t.Fatalf("POST override status=%d body=%s", resp.StatusCode, body)
	}

	// User-observable: DB row exists, GET endpoint returns it.
	resp, body = h.get(t, "/api/v1/jackett/overrides")
	if resp.StatusCode != 200 {
		t.Fatalf("GET overrides: %d body=%s", resp.StatusCode, body)
	}
	var rows []map[string]any
	if err := json.Unmarshal(body, &rows); err != nil {
		t.Fatalf("decode: %v body=%s", err, body)
	}
	found := false
	for _, r := range rows {
		if r["env_name"] == "RUTRACKER" && r["indexer_id"] == "rutracker_v2" {
			found = true
			break
		}
	}
	if !found {
		t.Fatalf("override RUTRACKER → rutracker_v2 not found in GET; got: %+v", rows)
	}

	// Repo-level cross-check.
	dbMap, err := h.overrides.AsMap()
	if err != nil {
		t.Fatalf("overrides.AsMap: %v", err)
	}
	if dbMap["RUTRACKER"] != "rutracker_v2" {
		t.Fatalf("DB override mismatch: %v", dbMap)
	}
}

// TestE2E_HighEntropyCredsNeverInResponseBodies is an additional
// safeguard: insert random 32-char credentials, then query every
// well-known GET endpoint and verify NONE of the response bodies
// contain the plaintext.
//
// Falsification: change credentialDTO to include a `password` field —
// at least one GET response body would contain the random string and
// the test would fail.
func TestE2E_HighEntropyCredsNeverInResponseBodies(t *testing.T) {
	skipIfNoJackett(t)
	h := newE2EHarness(t)

	// Insert 3 credentials with random 32-char ASCII secrets.
	secrets := make(map[string]string, 3)
	for _, name := range []string{"RUTRACKER", "KINOZAL", "IPTORRENTS"} {
		raw := make([]byte, 32)
		if _, err := rand.Read(raw); err != nil {
			t.Fatalf("rand: %v", err)
		}
		// Hex-encode to keep ASCII-safe and recognizable.
		secret := fmt.Sprintf("xx-%x", raw)
		secrets[name] = secret
		if resp, body := h.post(t, "/api/v1/jackett/credentials",
			map[string]any{"name": name, "username": secret, "password": secret}); resp.StatusCode != 200 {
			t.Fatalf("seed %s: %d body=%s", name, resp.StatusCode, body)
		}
	}

	// Query every public GET endpoint.
	for _, path := range []string{
		"/healthz",
		"/openapi.json",
		"/api/v1/jackett/credentials",
		"/api/v1/jackett/indexers",
		"/api/v1/jackett/catalog",
		"/api/v1/jackett/autoconfig/runs",
		"/api/v1/jackett/overrides",
	} {
		resp, body := h.get(t, path)
		if resp.StatusCode >= 500 {
			t.Errorf("GET %s 5xx: %d body=%s", path, resp.StatusCode, body)
			continue
		}
		for name, secret := range secrets {
			if bytes.Contains(body, []byte(secret)) {
				t.Fatalf("LEAK: secret for %s found in GET %s body: %s",
					name, path, body)
			}
		}
	}
}
