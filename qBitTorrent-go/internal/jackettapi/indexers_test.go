package jackettapi

import (
	"crypto/rand"
	"database/sql"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/db"
	"github.com/milos85vasic/qBitTorrent-go/internal/db/repos"
	"github.com/milos85vasic/qBitTorrent-go/internal/jackett"
)

// indexersHarness wires a fresh DB + httptest Jackett mock + IndexersDeps.
// Atomic counters on postCount/deleteCount/getCount let tests assert on
// Jackett-side side-effect occurrence (CONST-XII anti-bluff: a stub that
// returns 502 without touching Jackett would otherwise pass).
type indexersHarness struct {
	deps            *IndexersDeps
	conn            *sql.DB
	server          *httptest.Server
	postCount       int32
	deleteCount     int32
	getCount        int32
	lastPostBody    []byte // last POST /config body — assertion target
	templateFields  string // GET /config JSON body (per-test override)
	postStatus      int    // POST /config HTTP status
	deleteStatus    int    // DELETE indexer HTTP status
	getConfigStatus int    // GET /config HTTP status (also probed by /test)
}

func newIndexersHarness(t *testing.T) *indexersHarness {
	t.Helper()
	dir := t.TempDir()
	conn, err := db.Open(filepath.Join(dir, "t.db"))
	if err != nil {
		t.Fatalf("db.Open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		t.Fatalf("rand: %v", err)
	}

	h := &indexersHarness{
		conn:            conn,
		templateFields:  `[{"id":"username","value":""},{"id":"password","value":""}]`,
		postStatus:      200,
		deleteStatus:    200,
		getConfigStatus: 200,
	}

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == "POST" && r.URL.Path == "/UI/Dashboard":
			w.WriteHeader(302)
		case strings.HasSuffix(r.URL.Path, "/config") && r.Method == "GET":
			atomic.AddInt32(&h.getCount, 1)
			w.WriteHeader(h.getConfigStatus)
			if h.getConfigStatus < 400 {
				w.Header().Set("Content-Type", "application/json")
				_, _ = w.Write([]byte(h.templateFields))
			}
		case strings.HasSuffix(r.URL.Path, "/config") && r.Method == "POST":
			atomic.AddInt32(&h.postCount, 1)
			body, _ := io.ReadAll(r.Body)
			h.lastPostBody = body
			w.WriteHeader(h.postStatus)
		case r.Method == "DELETE":
			atomic.AddInt32(&h.deleteCount, 1)
			w.WriteHeader(h.deleteStatus)
		default:
			t.Logf("unexpected request: %s %s", r.Method, r.URL.Path)
			w.WriteHeader(404)
		}
	}))
	h.server = srv

	h.deps = &IndexersDeps{
		Indexers: repos.NewIndexers(conn),
		Creds:    repos.NewCredentials(conn, key),
		Catalog:  repos.NewCatalog(conn),
		Jackett:  jackett.NewClient(srv.URL, "test-api-key"),
	}
	t.Cleanup(func() {
		srv.Close()
		_ = conn.Close()
	})
	return h
}

func TestListIndexersEmpty(t *testing.T) {
	h := newIndexersHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/indexers", nil)
	h.deps.HandleListIndexers(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d", rec.Code)
	}
	if strings.TrimSpace(rec.Body.String()) != "[]" {
		t.Fatalf("empty list should serialize as []; got %q", rec.Body.String())
	}
}

func TestListIndexersWithRows(t *testing.T) {
	h := newIndexersHarness(t)
	// Seed the linked credential first so the FK on indexers.linked_credential_name resolves.
	if err := h.deps.Creds.Upsert("RUTRACKER", "userpass", strPtr("u"), strPtr("p"), nil); err != nil {
		t.Fatalf("seed cred: %v", err)
	}
	link := "RUTRACKER"
	if err := h.deps.Indexers.Upsert(&repos.Indexer{
		ID: "rutracker", DisplayName: "RuTracker.org", Type: "private",
		ConfiguredAtJackett: true, EnabledForSearch: true,
		LinkedCredentialName: &link,
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	if err := h.deps.Indexers.Upsert(&repos.Indexer{
		ID: "kinozalbiz", DisplayName: "Kinozal", Type: "private",
		ConfiguredAtJackett: true, EnabledForSearch: false,
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/indexers", nil)
	h.deps.HandleListIndexers(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	var dtos []map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &dtos); err != nil {
		t.Fatalf("decode: %v body=%s", err, rec.Body.String())
	}
	if len(dtos) != 2 {
		t.Fatalf("want 2 indexers, got %d body=%s", len(dtos), rec.Body.String())
	}
	// Order is by id ASC: kinozalbiz, rutracker.
	if dtos[0]["id"] != "kinozalbiz" || dtos[1]["id"] != "rutracker" {
		t.Fatalf("order: %+v", dtos)
	}
	if dtos[0]["enabled_for_search"] != false {
		t.Fatalf("kinozalbiz enabled_for_search: %+v", dtos[0])
	}
	if dtos[1]["linked_credential_name"] != "RUTRACKER" {
		t.Fatalf("rutracker linked_credential_name: %+v", dtos[1])
	}
	if dtos[1]["display_name"] != "RuTracker.org" {
		t.Fatalf("rutracker display_name: %+v", dtos[1])
	}
}

func TestConfigureIndexerHappyPath(t *testing.T) {
	h := newIndexersHarness(t)
	if err := h.deps.Creds.Upsert("RUTRACKER", "userpass", strPtr("uname"), strPtr("pwd"), nil); err != nil {
		t.Fatalf("seed cred: %v", err)
	}
	// Seed catalog so the row gets the right display_name + type.
	if err := h.deps.Catalog.Upsert(&repos.CatalogEntry{
		ID: "rutracker", DisplayName: "RuTracker.org", Type: "private",
		TemplateFieldsJSON: "[]", CachedAt: time.Now().UTC(),
	}); err != nil {
		t.Fatalf("seed catalog: %v", err)
	}

	body := `{"credential_name":"RUTRACKER"}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/indexers/rutracker", strings.NewReader(body))
	h.deps.HandleConfigureIndexer(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}

	// Anti-bluff: response DTO must reflect post-state.
	var dto map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &dto); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if dto["id"] != "rutracker" {
		t.Fatalf("id: %+v", dto)
	}
	if dto["configured_at_jackett"] != true {
		t.Fatalf("configured_at_jackett: %+v", dto)
	}
	if dto["linked_credential_name"] != "RUTRACKER" {
		t.Fatalf("linked_credential_name: %+v", dto)
	}
	if dto["display_name"] != "RuTracker.org" {
		t.Fatalf("display_name: %+v", dto)
	}
	if dto["type"] != "private" {
		t.Fatalf("type: %+v", dto)
	}

	// Anti-bluff: DB row exists with same fields.
	rows, err := h.deps.Indexers.List()
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if len(rows) != 1 || rows[0].ID != "rutracker" {
		t.Fatalf("DB rows: %+v", rows)
	}
	if !rows[0].ConfiguredAtJackett || !rows[0].EnabledForSearch {
		t.Fatalf("flags: %+v", rows[0])
	}
	if rows[0].LinkedCredentialName == nil || *rows[0].LinkedCredentialName != "RUTRACKER" {
		t.Fatalf("link: %+v", rows[0].LinkedCredentialName)
	}

	// Anti-bluff: Jackett actually got the POST with credential plaintext.
	if atomic.LoadInt32(&h.postCount) != 1 {
		t.Fatalf("expected 1 POST to Jackett, got %d", h.postCount)
	}
	if !strings.Contains(string(h.lastPostBody), "uname") {
		t.Fatalf("posted body missing username: %s", h.lastPostBody)
	}
	if !strings.Contains(string(h.lastPostBody), "pwd") {
		t.Fatalf("posted body missing password: %s", h.lastPostBody)
	}
}

func TestConfigureIndexerCredentialNotFound(t *testing.T) {
	h := newIndexersHarness(t)
	body := `{"credential_name":"NOSUCH"}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/indexers/rutracker", strings.NewReader(body))
	h.deps.HandleConfigureIndexer(rec, req)
	if rec.Code != 404 {
		t.Fatalf("expected 404, got %d body=%s", rec.Code, rec.Body.String())
	}
	// Anti-bluff: no DB row, no Jackett POST.
	rows, _ := h.deps.Indexers.List()
	if len(rows) != 0 {
		t.Fatalf("DB row leaked: %+v", rows)
	}
	if atomic.LoadInt32(&h.postCount) != 0 {
		t.Fatalf("Jackett POST should not have happened: %d", h.postCount)
	}
}

func TestConfigureIndexerMissingCredentialName(t *testing.T) {
	h := newIndexersHarness(t)
	body := `{}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/indexers/rutracker", strings.NewReader(body))
	h.deps.HandleConfigureIndexer(rec, req)
	if rec.Code != 400 {
		t.Fatalf("expected 400, got %d body=%s", rec.Code, rec.Body.String())
	}
}

func TestConfigureIndexerNoCompatibleFields(t *testing.T) {
	h := newIndexersHarness(t)
	// Template wants cookie, but the cred is userpass.
	h.templateFields = `[{"id":"cookie","value":""}]`
	if err := h.deps.Creds.Upsert("RUTRACKER", "userpass", strPtr("u"), strPtr("p"), nil); err != nil {
		t.Fatalf("seed cred: %v", err)
	}
	body := `{"credential_name":"RUTRACKER"}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/indexers/rutracker", strings.NewReader(body))
	h.deps.HandleConfigureIndexer(rec, req)
	if rec.Code != 400 {
		t.Fatalf("expected 400, got %d body=%s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), "no_compatible_credential_fields_for_indexer") {
		t.Fatalf("error code missing: %s", rec.Body.String())
	}
	// Anti-bluff: no DB row, no Jackett POST.
	rows, _ := h.deps.Indexers.List()
	if len(rows) != 0 {
		t.Fatalf("DB row created despite no-fill: %+v", rows)
	}
	if atomic.LoadInt32(&h.postCount) != 0 {
		t.Fatalf("Jackett POST should not have happened: %d", h.postCount)
	}
}

func TestConfigureIndexerJackettPostFails(t *testing.T) {
	h := newIndexersHarness(t)
	h.postStatus = 500
	if err := h.deps.Creds.Upsert("RUTRACKER", "userpass", strPtr("u"), strPtr("p"), nil); err != nil {
		t.Fatalf("seed cred: %v", err)
	}
	body := `{"credential_name":"RUTRACKER"}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/indexers/rutracker", strings.NewReader(body))
	h.deps.HandleConfigureIndexer(rec, req)
	if rec.Code != 502 {
		t.Fatalf("expected 502, got %d body=%s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), "jackett_post_failed") {
		t.Fatalf("error code missing: %s", rec.Body.String())
	}
	// Anti-bluff: no DB row created.
	rows, _ := h.deps.Indexers.List()
	if len(rows) != 0 {
		t.Fatalf("DB row should not exist on Jackett POST failure: %+v", rows)
	}
}

func TestConfigureIndexerTemplateFetchFails(t *testing.T) {
	h := newIndexersHarness(t)
	h.getConfigStatus = 500
	if err := h.deps.Creds.Upsert("RUTRACKER", "userpass", strPtr("u"), strPtr("p"), nil); err != nil {
		t.Fatalf("seed cred: %v", err)
	}
	body := `{"credential_name":"RUTRACKER"}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/indexers/rutracker", strings.NewReader(body))
	h.deps.HandleConfigureIndexer(rec, req)
	if rec.Code != 502 {
		t.Fatalf("expected 502, got %d body=%s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), "template_fetch_failed") {
		t.Fatalf("error code missing: %s", rec.Body.String())
	}
	rows, _ := h.deps.Indexers.List()
	if len(rows) != 0 {
		t.Fatalf("DB row should not exist on template-fetch failure: %+v", rows)
	}
}

func TestConfigureIndexerExtraFieldsOverrideTemplate(t *testing.T) {
	h := newIndexersHarness(t)
	if err := h.deps.Creds.Upsert("RUTRACKER", "userpass", strPtr("u"), strPtr("p"), nil); err != nil {
		t.Fatalf("seed: %v", err)
	}
	// Template has username + password; extra_fields override password to a custom value.
	body := `{"credential_name":"RUTRACKER","extra_fields":[{"id":"password","value":"override-pass"}]}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/indexers/rutracker", strings.NewReader(body))
	h.deps.HandleConfigureIndexer(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(string(h.lastPostBody), "override-pass") {
		t.Fatalf("extra_fields override not applied: %s", h.lastPostBody)
	}
	// Username from credential still present.
	if !strings.Contains(string(h.lastPostBody), `"u"`) {
		t.Fatalf("posted body missing username: %s", h.lastPostBody)
	}
}

func TestDeleteIndexerRemovesFromDBAndCallsJackett(t *testing.T) {
	h := newIndexersHarness(t)
	if err := h.deps.Indexers.Upsert(&repos.Indexer{
		ID: "rutracker", DisplayName: "RuTracker", Type: "private",
		ConfiguredAtJackett: true, EnabledForSearch: true,
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("DELETE", "/api/v1/jackett/indexers/rutracker", nil)
	h.deps.HandleDeleteIndexer(rec, req)
	if rec.Code != 204 {
		t.Fatalf("expected 204, got %d body=%s", rec.Code, rec.Body.String())
	}
	// Anti-bluff: row gone + Jackett DELETE called.
	rows, _ := h.deps.Indexers.List()
	if len(rows) != 0 {
		t.Fatalf("DB row not deleted: %+v", rows)
	}
	if atomic.LoadInt32(&h.deleteCount) != 1 {
		t.Fatalf("expected 1 DELETE to Jackett, got %d", h.deleteCount)
	}
}

func TestDeleteIndexerJackettErrorDoesntBlockDB(t *testing.T) {
	h := newIndexersHarness(t)
	h.deleteStatus = 500
	if err := h.deps.Indexers.Upsert(&repos.Indexer{
		ID: "rutracker", DisplayName: "RuTracker", Type: "private",
		ConfiguredAtJackett: true, EnabledForSearch: true,
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("DELETE", "/api/v1/jackett/indexers/rutracker", nil)
	h.deps.HandleDeleteIndexer(rec, req)
	if rec.Code != 204 {
		t.Fatalf("expected 204 even on Jackett error, got %d body=%s", rec.Code, rec.Body.String())
	}
	rows, _ := h.deps.Indexers.List()
	if len(rows) != 0 {
		t.Fatalf("DB row not deleted: %+v", rows)
	}
}

func TestDeleteIndexerEmptyPath400(t *testing.T) {
	h := newIndexersHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("DELETE", "/api/v1/jackett/indexers/", nil)
	h.deps.HandleDeleteIndexer(rec, req)
	if rec.Code != 400 {
		t.Fatalf("expected 400, got %d", rec.Code)
	}
}

func TestPatchIndexerEnabledForSearch(t *testing.T) {
	h := newIndexersHarness(t)
	if err := h.deps.Indexers.Upsert(&repos.Indexer{
		ID: "rutracker", DisplayName: "RuTracker", Type: "private",
		ConfiguredAtJackett: true, EnabledForSearch: true,
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	body := `{"enabled_for_search":false}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("PATCH", "/api/v1/jackett/indexers/rutracker", strings.NewReader(body))
	h.deps.HandlePatchIndexer(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	// Anti-bluff: DB row reflects the toggle.
	got, err := h.deps.Indexers.Get("rutracker")
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if got.EnabledForSearch {
		t.Fatalf("DB still has enabled=true")
	}
	// Response DTO matches.
	var dto map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &dto); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if dto["enabled_for_search"] != false {
		t.Fatalf("response DTO: %+v", dto)
	}
}

func TestPatchIndexerNoFieldReturns400(t *testing.T) {
	h := newIndexersHarness(t)
	if err := h.deps.Indexers.Upsert(&repos.Indexer{
		ID: "rutracker", DisplayName: "RuTracker", Type: "private",
		ConfiguredAtJackett: true, EnabledForSearch: true,
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	body := `{}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("PATCH", "/api/v1/jackett/indexers/rutracker", strings.NewReader(body))
	h.deps.HandlePatchIndexer(rec, req)
	if rec.Code != 400 {
		t.Fatalf("expected 400, got %d body=%s", rec.Code, rec.Body.String())
	}
}

func TestPatchIndexerNotFound(t *testing.T) {
	h := newIndexersHarness(t)
	body := `{"enabled_for_search":false}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("PATCH", "/api/v1/jackett/indexers/missing", strings.NewReader(body))
	h.deps.HandlePatchIndexer(rec, req)
	if rec.Code != 404 {
		t.Fatalf("expected 404, got %d body=%s", rec.Code, rec.Body.String())
	}
}

func TestTestIndexerOK(t *testing.T) {
	h := newIndexersHarness(t)
	if err := h.deps.Indexers.Upsert(&repos.Indexer{
		ID: "rutracker", DisplayName: "RuTracker", Type: "private",
		ConfiguredAtJackett: true, EnabledForSearch: true,
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/indexers/rutracker/test", nil)
	h.deps.HandleTestIndexer(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	var res map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &res); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if res["status"] != "ok" {
		t.Fatalf("status: %+v", res)
	}
	// Anti-bluff: DB stamped last_test_status="ok" and last_test_at non-nil.
	got, err := h.deps.Indexers.Get("rutracker")
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if got.LastTestStatus == nil || *got.LastTestStatus != "ok" {
		t.Fatalf("LastTestStatus: %+v", got.LastTestStatus)
	}
	if got.LastTestAt == nil {
		t.Fatalf("LastTestAt should be set")
	}
}

func TestTestIndexerAuthFailed(t *testing.T) {
	h := newIndexersHarness(t)
	h.getConfigStatus = 401
	if err := h.deps.Indexers.Upsert(&repos.Indexer{
		ID: "rutracker", DisplayName: "RuTracker", Type: "private",
		ConfiguredAtJackett: true, EnabledForSearch: true,
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/indexers/rutracker/test", nil)
	h.deps.HandleTestIndexer(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	var res map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &res); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if res["status"] != "auth_failed" {
		t.Fatalf("expected auth_failed, got %+v", res)
	}
	got, _ := h.deps.Indexers.Get("rutracker")
	if got.LastTestStatus == nil || *got.LastTestStatus != "auth_failed" {
		t.Fatalf("LastTestStatus: %+v", got.LastTestStatus)
	}
}

func TestTestIndexerUnreachable(t *testing.T) {
	h := newIndexersHarness(t)
	if err := h.deps.Indexers.Upsert(&repos.Indexer{
		ID: "rutracker", DisplayName: "RuTracker", Type: "private",
		ConfiguredAtJackett: true, EnabledForSearch: true,
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	// Repoint at a port that won't connect.
	h.deps.Jackett = jackett.NewClient("http://127.0.0.1:1", "test-api-key")
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/indexers/rutracker/test", nil)
	h.deps.HandleTestIndexer(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	var res map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &res); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if res["status"] != "unreachable" {
		t.Fatalf("expected unreachable, got %+v", res)
	}
	got, _ := h.deps.Indexers.Get("rutracker")
	if got.LastTestStatus == nil || *got.LastTestStatus != "unreachable" {
		t.Fatalf("LastTestStatus: %+v", got.LastTestStatus)
	}
}

func TestTestIndexerEmptyPath400(t *testing.T) {
	h := newIndexersHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/indexers//test", nil)
	h.deps.HandleTestIndexer(rec, req)
	if rec.Code != 400 {
		t.Fatalf("expected 400, got %d body=%s", rec.Code, rec.Body.String())
	}
}

func TestPathTraversalRejected(t *testing.T) {
	h := newIndexersHarness(t)
	cases := []struct {
		method  string
		path    string
		body    string
		handler func(http.ResponseWriter, *http.Request)
	}{
		{"POST", "/api/v1/jackett/indexers/RUTRACKER/extra", `{"credential_name":"X"}`, h.deps.HandleConfigureIndexer},
		{"DELETE", "/api/v1/jackett/indexers/RUTRACKER/extra", "", h.deps.HandleDeleteIndexer},
		{"PATCH", "/api/v1/jackett/indexers/RUTRACKER/extra", `{"enabled_for_search":false}`, h.deps.HandlePatchIndexer},
		{"POST", "/api/v1/jackett/indexers/RUTRACKER/extra/test", "", h.deps.HandleTestIndexer},
	}
	for _, c := range cases {
		t.Run(c.method+" "+c.path, func(t *testing.T) {
			var body io.Reader
			if c.body != "" {
				body = strings.NewReader(c.body)
			}
			rec := httptest.NewRecorder()
			req := httptest.NewRequest(c.method, c.path, body)
			c.handler(rec, req)
			if rec.Code != 400 {
				t.Fatalf("expected 400, got %d body=%s", rec.Code, rec.Body.String())
			}
		})
	}
}
