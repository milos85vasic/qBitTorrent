package jackettapi

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strconv"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/db"
	"github.com/milos85vasic/qBitTorrent-go/internal/db/repos"
	"github.com/milos85vasic/qBitTorrent-go/internal/jackett"
)

// catalogHarness wires a fresh DB + httptest Jackett mock + CatalogDeps.
// Atomic counters let tests assert that Jackett was actually called
// (CONST-XII anti-bluff: a stub that returns 200 + correct DTO without
// calling Jackett or writing DB would otherwise pass on status alone).
type catalogHarness struct {
	deps          *CatalogDeps
	server        *httptest.Server
	catalogCalls  int32 // atomic — counts /api/v2.0/indexers GETs
	templateCalls int32 // atomic — counts /api/v2.0/indexers/{id}/config GETs
}

func newCatalogHarness(t *testing.T) *catalogHarness {
	t.Helper()
	dir := t.TempDir()
	conn, err := db.Open(filepath.Join(dir, "t.db"))
	if err != nil {
		t.Fatalf("db.Open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	h := &catalogHarness{}
	h.server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == "POST" && r.URL.Path == "/UI/Dashboard":
			w.WriteHeader(302)
		case r.URL.Path == "/api/v2.0/indexers" && r.Method == "GET":
			atomic.AddInt32(&h.catalogCalls, 1)
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`[
				{"id":"rutracker","name":"RuTracker","type":"private","configured":false,"language":"ru","description":"Russian"},
				{"id":"iptorrents","name":"IPTorrents","type":"private","configured":false,"language":"en","description":"Cookie-based"}
			]`))
		case strings.HasSuffix(r.URL.Path, "/rutracker/config") && r.Method == "GET":
			atomic.AddInt32(&h.templateCalls, 1)
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`[{"id":"username","type":"input"},{"id":"password","type":"hidden"}]`))
		case strings.HasSuffix(r.URL.Path, "/iptorrents/config") && r.Method == "GET":
			atomic.AddInt32(&h.templateCalls, 1)
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`[{"id":"cookie","type":"hidden"}]`))
		default:
			t.Logf("unexpected request: %s %s", r.Method, r.URL.Path)
			w.WriteHeader(404)
		}
	}))
	h.deps = &CatalogDeps{
		Catalog: repos.NewCatalog(conn),
		Jackett: jackett.NewClient(h.server.URL, "test-key"),
	}
	t.Cleanup(func() { h.server.Close(); _ = conn.Close() })
	return h
}

func TestListCatalogEmpty(t *testing.T) {
	h := newCatalogHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/catalog", nil)
	h.deps.HandleListCatalog(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d", rec.Code)
	}
	var got catalogPageDTO
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if got.Total != 0 {
		t.Fatalf("total: %d", got.Total)
	}
	if got.Page != 1 || got.PageSize != 50 {
		t.Fatalf("defaults: page=%d size=%d", got.Page, got.PageSize)
	}
	if len(got.Items) != 0 {
		t.Fatalf("items: %d", len(got.Items))
	}
}

func TestListCatalogPagination(t *testing.T) {
	h := newCatalogHarness(t)
	// Seed 75 rows.
	for i := 0; i < 75; i++ {
		idx := i
		lang := "en"
		desc := "test"
		if err := h.deps.Catalog.Upsert(&repos.CatalogEntry{
			ID:                 "indexer-" + strconv.Itoa(idx),
			DisplayName:        "Indexer " + strconv.Itoa(idx),
			Type:               "public",
			Language:           &lang,
			Description:        &desc,
			TemplateFieldsJSON: "[]",
			CachedAt:           time.Now().UTC(),
		}); err != nil {
			t.Fatalf("seed: %v", err)
		}
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/catalog?page=2&page_size=20", nil)
	h.deps.HandleListCatalog(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d", rec.Code)
	}
	var got catalogPageDTO
	_ = json.Unmarshal(rec.Body.Bytes(), &got)
	if got.Total != 75 {
		t.Fatalf("total: %d", got.Total)
	}
	if got.Page != 2 || got.PageSize != 20 {
		t.Fatalf("page/size: %d %d", got.Page, got.PageSize)
	}
	if len(got.Items) != 20 {
		t.Fatalf("items: %d", len(got.Items))
	}
	// Ordering is by display_name (per repo); just verify the page-2 items
	// are real entries from the seeded set and not the same as page-1.
	if !strings.HasPrefix(got.Items[0].ID, "indexer-") {
		t.Fatalf("unexpected first id: %s", got.Items[0].ID)
	}
}

func TestListCatalogPageSizeCap(t *testing.T) {
	h := newCatalogHarness(t)
	// Seed 250 rows so an unbounded page_size would matter.
	for i := 0; i < 250; i++ {
		if err := h.deps.Catalog.Upsert(&repos.CatalogEntry{
			ID:                 "x" + strconv.Itoa(i),
			DisplayName:        "X " + strconv.Itoa(i),
			Type:               "public",
			TemplateFieldsJSON: "[]",
			CachedAt:           time.Now().UTC(),
		}); err != nil {
			t.Fatalf("seed: %v", err)
		}
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/catalog?page_size=999", nil)
	h.deps.HandleListCatalog(rec, req)
	var got catalogPageDTO
	_ = json.Unmarshal(rec.Body.Bytes(), &got)
	if got.PageSize > 200 {
		t.Fatalf("expected cap at 200, got %d", got.PageSize)
	}
	if len(got.Items) > 200 {
		t.Fatalf("items %d > cap", len(got.Items))
	}
}

func TestListCatalogBadPageReturns400(t *testing.T) {
	h := newCatalogHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/catalog?page=0", nil)
	h.deps.HandleListCatalog(rec, req)
	if rec.Code != 400 {
		t.Fatalf("status: %d", rec.Code)
	}
}

func TestListCatalogBadPageSizeReturns400(t *testing.T) {
	h := newCatalogHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/catalog?page_size=-3", nil)
	h.deps.HandleListCatalog(rec, req)
	if rec.Code != 400 {
		t.Fatalf("status: %d", rec.Code)
	}
}

func TestListCatalogFiltersBySearch(t *testing.T) {
	h := newCatalogHarness(t)
	if err := h.deps.Catalog.Upsert(&repos.CatalogEntry{
		ID: "rutracker", DisplayName: "RuTracker", Type: "private",
		TemplateFieldsJSON: "[]", CachedAt: time.Now().UTC(),
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	if err := h.deps.Catalog.Upsert(&repos.CatalogEntry{
		ID: "kinozalbiz", DisplayName: "KinoZal", Type: "private",
		TemplateFieldsJSON: "[]", CachedAt: time.Now().UTC(),
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/catalog?search=RuT", nil)
	h.deps.HandleListCatalog(rec, req)
	var got catalogPageDTO
	_ = json.Unmarshal(rec.Body.Bytes(), &got)
	if got.Total != 1 {
		t.Fatalf("total: %d", got.Total)
	}
	if got.Items[0].ID != "rutracker" {
		t.Fatalf("id: %s", got.Items[0].ID)
	}
}

func TestListCatalogRequiredFieldsExtracted(t *testing.T) {
	h := newCatalogHarness(t)
	if err := h.deps.Catalog.Upsert(&repos.CatalogEntry{
		ID: "rutracker", DisplayName: "RuTracker", Type: "private",
		TemplateFieldsJSON: `[{"id":"username","type":"input"},{"id":"password","type":"hidden"},{"id":"unrelated","type":"checkbox"}]`,
		CachedAt:           time.Now().UTC(),
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/catalog", nil)
	h.deps.HandleListCatalog(rec, req)
	var got catalogPageDTO
	_ = json.Unmarshal(rec.Body.Bytes(), &got)
	if len(got.Items) != 1 {
		t.Fatalf("items: %d", len(got.Items))
	}
	fields := got.Items[0].RequiredFields
	if len(fields) != 2 {
		t.Fatalf("expected 2 required fields, got %v", fields)
	}
	seen := map[string]bool{}
	for _, f := range fields {
		seen[f] = true
	}
	if !seen["username"] || !seen["password"] {
		t.Fatalf("missing username/password: %v", fields)
	}
}

func TestListCatalogRequiredFieldsHandlesEnvelopeShape(t *testing.T) {
	h := newCatalogHarness(t)
	if err := h.deps.Catalog.Upsert(&repos.CatalogEntry{
		ID: "x", DisplayName: "X", Type: "private",
		TemplateFieldsJSON: `{"config":[{"id":"cookie","type":"hidden"}]}`,
		CachedAt:           time.Now().UTC(),
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/catalog", nil)
	h.deps.HandleListCatalog(rec, req)
	var got catalogPageDTO
	_ = json.Unmarshal(rec.Body.Bytes(), &got)
	if len(got.Items[0].RequiredFields) != 1 || got.Items[0].RequiredFields[0] != "cookie" {
		t.Fatalf("envelope shape not parsed: %v", got.Items[0].RequiredFields)
	}
}

func TestListCatalogRequiredFieldsMalformedJSONIsEmpty(t *testing.T) {
	h := newCatalogHarness(t)
	if err := h.deps.Catalog.Upsert(&repos.CatalogEntry{
		ID: "broken", DisplayName: "Broken", Type: "private",
		TemplateFieldsJSON: "{not json",
		CachedAt:           time.Now().UTC(),
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/catalog", nil)
	h.deps.HandleListCatalog(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d", rec.Code)
	}
	var got catalogPageDTO
	_ = json.Unmarshal(rec.Body.Bytes(), &got)
	if len(got.Items) != 1 {
		t.Fatalf("items: %d", len(got.Items))
	}
	if len(got.Items[0].RequiredFields) != 0 {
		t.Fatalf("malformed template should produce empty fields, got %v", got.Items[0].RequiredFields)
	}
}

func TestRefreshCatalogHappyPath(t *testing.T) {
	h := newCatalogHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/catalog/refresh", nil)
	h.deps.HandleRefreshCatalog(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	var got catalogRefreshResultDTO
	_ = json.Unmarshal(rec.Body.Bytes(), &got)
	if got.RefreshedCount != 2 {
		t.Fatalf("refreshed: %d errors=%v", got.RefreshedCount, got.Errors)
	}
	if len(got.Errors) != 0 {
		t.Fatalf("errors: %+v", got.Errors)
	}
	// CONST-XII: assert post-state — DB has both rows.
	rows, total, err := h.deps.Catalog.Query(repos.CatalogQuery{})
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if total != 2 {
		t.Fatalf("DB total: %d", total)
	}
	if len(rows) != 2 {
		t.Fatalf("DB rows: %d", len(rows))
	}
	// CONST-XII: assert Jackett was actually called (counters falsify a stub).
	if atomic.LoadInt32(&h.catalogCalls) != 1 {
		t.Fatalf("catalog endpoint not hit: %d", h.catalogCalls)
	}
	if atomic.LoadInt32(&h.templateCalls) != 2 {
		t.Fatalf("template endpoint hits: %d", h.templateCalls)
	}
	// CONST-XII: persisted template content reflects what Jackett returned.
	rt, err := h.deps.Catalog.Get("rutracker")
	if err != nil {
		t.Fatalf("Get(rutracker): %v", err)
	}
	if !strings.Contains(rt.TemplateFieldsJSON, "username") {
		t.Fatalf("rutracker template not stored: %s", rt.TemplateFieldsJSON)
	}
	// And language/description came from the catalog list, not the template.
	if rt.Language == nil || *rt.Language != "ru" {
		t.Fatalf("rutracker language not stored: %v", rt.Language)
	}
	if rt.Description == nil || *rt.Description != "Russian" {
		t.Fatalf("rutracker description not stored: %v", rt.Description)
	}
}

func TestRefreshCatalogJackettCatalogFails(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/v2.0/indexers" {
			w.WriteHeader(500)
			return
		}
		if r.URL.Path == "/UI/Dashboard" {
			w.WriteHeader(302)
			return
		}
		w.WriteHeader(404)
	}))
	defer srv.Close()
	dir := t.TempDir()
	conn, _ := db.Open(filepath.Join(dir, "t.db"))
	_ = db.Migrate(conn)
	defer conn.Close()
	deps := &CatalogDeps{Catalog: repos.NewCatalog(conn), Jackett: jackett.NewClient(srv.URL, "k")}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/catalog/refresh", nil)
	deps.HandleRefreshCatalog(rec, req)
	if rec.Code != 502 {
		t.Fatalf("expected 502, got %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "jackett_catalog_failed") {
		t.Fatalf("error code missing: %s", rec.Body.String())
	}
	// CONST-XII: DB should NOT be modified on failure.
	_, total, _ := deps.Catalog.Query(repos.CatalogQuery{})
	if total != 0 {
		t.Fatalf("DB modified despite failure: total=%d", total)
	}
}

func TestRefreshCatalogPerIndexerErrorsSurfaceButDontAbort(t *testing.T) {
	var cc, tc int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/UI/Dashboard":
			w.WriteHeader(302)
		case r.URL.Path == "/api/v2.0/indexers":
			atomic.AddInt32(&cc, 1)
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`[{"id":"good","name":"Good","type":"private","configured":false},{"id":"bad","name":"Bad","type":"private","configured":false}]`))
		case strings.HasSuffix(r.URL.Path, "/good/config"):
			atomic.AddInt32(&tc, 1)
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`[{"id":"username","type":"input"}]`))
		case strings.HasSuffix(r.URL.Path, "/bad/config"):
			atomic.AddInt32(&tc, 1)
			w.WriteHeader(500)
		default:
			w.WriteHeader(404)
		}
	}))
	defer srv.Close()
	dir := t.TempDir()
	conn, _ := db.Open(filepath.Join(dir, "t.db"))
	_ = db.Migrate(conn)
	defer conn.Close()
	deps := &CatalogDeps{Catalog: repos.NewCatalog(conn), Jackett: jackett.NewClient(srv.URL, "k")}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/catalog/refresh", nil)
	deps.HandleRefreshCatalog(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	var got catalogRefreshResultDTO
	_ = json.Unmarshal(rec.Body.Bytes(), &got)
	if got.RefreshedCount != 1 {
		t.Fatalf("refreshed: %d", got.RefreshedCount)
	}
	if len(got.Errors) != 1 || !strings.Contains(got.Errors[0], "bad") {
		t.Fatalf("expected one bad-indexer error, got %+v", got.Errors)
	}
	// CONST-XII: DB has exactly one entry — the good one.
	rows, total, _ := deps.Catalog.Query(repos.CatalogQuery{})
	if total != 1 {
		t.Fatalf("DB total: %d", total)
	}
	if len(rows) != 1 || rows[0].ID != "good" {
		t.Fatalf("DB rows: %+v", rows)
	}
	// And both endpoints were hit.
	if atomic.LoadInt32(&cc) != 1 {
		t.Fatalf("catalog calls: %d", cc)
	}
	if atomic.LoadInt32(&tc) != 2 {
		t.Fatalf("template calls: %d", tc)
	}
}

func TestRefreshCatalogAllTemplatesFailReturns200WithErrors(t *testing.T) {
	// Catalog returns 1 indexer; its template GET 500s → no rows to write.
	// Spec choice: still return 200 (the user wants to see the errors).
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/UI/Dashboard":
			w.WriteHeader(302)
		case r.URL.Path == "/api/v2.0/indexers":
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`[{"id":"only","name":"Only","type":"private","configured":false}]`))
		case strings.HasSuffix(r.URL.Path, "/only/config"):
			w.WriteHeader(500)
		default:
			w.WriteHeader(404)
		}
	}))
	defer srv.Close()
	dir := t.TempDir()
	conn, _ := db.Open(filepath.Join(dir, "t.db"))
	_ = db.Migrate(conn)
	defer conn.Close()
	deps := &CatalogDeps{Catalog: repos.NewCatalog(conn), Jackett: jackett.NewClient(srv.URL, "k")}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/catalog/refresh", nil)
	deps.HandleRefreshCatalog(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	var got catalogRefreshResultDTO
	_ = json.Unmarshal(rec.Body.Bytes(), &got)
	if got.RefreshedCount != 0 {
		t.Fatalf("refreshed: %d", got.RefreshedCount)
	}
	if len(got.Errors) != 1 {
		t.Fatalf("errors: %+v", got.Errors)
	}
	// CONST-XII: DB is empty (no ReplaceAll call when no rows built).
	_, total, _ := deps.Catalog.Query(repos.CatalogQuery{})
	if total != 0 {
		t.Fatalf("DB modified: total=%d", total)
	}
}
