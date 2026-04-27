package jackettapi

import (
	"encoding/json"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"github.com/milos85vasic/qBitTorrent-go/internal/db"
	"github.com/milos85vasic/qBitTorrent-go/internal/db/repos"
)

// overridesHarness wires a fresh DB + OverridesDeps for each test.
type overridesHarness struct {
	deps *OverridesDeps
}

func newOverridesHarness(t *testing.T) *overridesHarness {
	t.Helper()
	dir := t.TempDir()
	conn, err := db.Open(filepath.Join(dir, "t.db"))
	if err != nil {
		t.Fatalf("db.Open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	h := &overridesHarness{deps: &OverridesDeps{Repo: repos.NewOverrides(conn)}}
	t.Cleanup(func() { _ = conn.Close() })
	return h
}

func TestListOverridesEmpty(t *testing.T) {
	h := newOverridesHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/overrides", nil)
	h.deps.HandleListOverrides(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d", rec.Code)
	}
	var got []overrideDTO
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v body=%s", err, rec.Body.String())
	}
	if len(got) != 0 {
		t.Fatalf("want empty: %+v", got)
	}
}

func TestPostOverrideAddsRow(t *testing.T) {
	h := newOverridesHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/overrides",
		strings.NewReader(`{"env_name":"RUTRACKER","indexer_id":"rutracker_v2"}`))
	h.deps.HandleUpsertOverride(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	var got overrideDTO
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if got.EnvName != "RUTRACKER" || got.IndexerID != "rutracker_v2" {
		t.Fatalf("dto: %+v", got)
	}
	if got.CreatedAt.IsZero() {
		t.Fatalf("created_at not populated")
	}
	// CONST-XII: post-state assertion. A handler that returned the right
	// JSON without persisting would fail this check.
	rows, err := h.deps.Repo.List()
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(rows) != 1 || rows[0].EnvName != "RUTRACKER" || rows[0].IndexerID != "rutracker_v2" {
		t.Fatalf("DB state: %+v", rows)
	}
}

func TestPostOverrideUpsertSemantics(t *testing.T) {
	h := newOverridesHarness(t)
	if err := h.deps.Repo.Upsert("RUTRACKER", "old_id"); err != nil {
		t.Fatalf("seed: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/overrides",
		strings.NewReader(`{"env_name":"RUTRACKER","indexer_id":"new_id"}`))
	h.deps.HandleUpsertOverride(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d", rec.Code)
	}
	rows, _ := h.deps.Repo.List()
	if len(rows) != 1 {
		t.Fatalf("expected 1 row, got %d", len(rows))
	}
	if rows[0].IndexerID != "new_id" {
		t.Fatalf("upsert didn't update: %s", rows[0].IndexerID)
	}
}

func TestPostOverrideEnvNameUppercased(t *testing.T) {
	h := newOverridesHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/overrides",
		strings.NewReader(`{"env_name":"rutracker","indexer_id":"x"}`))
	h.deps.HandleUpsertOverride(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d", rec.Code)
	}
	rows, _ := h.deps.Repo.List()
	if len(rows) != 1 || rows[0].EnvName != "RUTRACKER" {
		t.Fatalf("env_name not uppercased: %+v", rows)
	}
}

func TestPostOverrideMissingFields400(t *testing.T) {
	h := newOverridesHarness(t)
	for _, body := range []string{
		`{"env_name":"X"}`,
		`{"indexer_id":"x"}`,
		`{}`,
		`{"env_name":"","indexer_id":""}`,
	} {
		rec := httptest.NewRecorder()
		req := httptest.NewRequest("POST", "/api/v1/jackett/overrides", strings.NewReader(body))
		h.deps.HandleUpsertOverride(rec, req)
		if rec.Code != 400 {
			t.Fatalf("body %q: want 400, got %d", body, rec.Code)
		}
	}
}

func TestPostOverrideBadJSON400(t *testing.T) {
	h := newOverridesHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/overrides", strings.NewReader("not json"))
	h.deps.HandleUpsertOverride(rec, req)
	if rec.Code != 400 {
		t.Fatalf("status: %d", rec.Code)
	}
}

func TestDeleteOverrideRemovesRow(t *testing.T) {
	h := newOverridesHarness(t)
	if err := h.deps.Repo.Upsert("RUTRACKER", "rutracker_v2"); err != nil {
		t.Fatalf("seed: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("DELETE", "/api/v1/jackett/overrides/RUTRACKER", nil)
	h.deps.HandleDeleteOverride(rec, req)
	if rec.Code != 204 {
		t.Fatalf("status: %d", rec.Code)
	}
	rows, _ := h.deps.Repo.List()
	if len(rows) != 0 {
		t.Fatalf("DB still has rows: %+v", rows)
	}
}

func TestDeleteOverrideIdempotent(t *testing.T) {
	h := newOverridesHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("DELETE", "/api/v1/jackett/overrides/MISSING", nil)
	h.deps.HandleDeleteOverride(rec, req)
	if rec.Code != 204 {
		t.Fatalf("idempotent delete: status %d", rec.Code)
	}
}

func TestDeleteOverrideEmptyPath400(t *testing.T) {
	h := newOverridesHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("DELETE", "/api/v1/jackett/overrides/", nil)
	h.deps.HandleDeleteOverride(rec, req)
	if rec.Code != 400 {
		t.Fatalf("status: %d", rec.Code)
	}
}

func TestDeleteOverrideNestedPath400(t *testing.T) {
	h := newOverridesHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("DELETE", "/api/v1/jackett/overrides/X/extra", nil)
	h.deps.HandleDeleteOverride(rec, req)
	if rec.Code != 400 {
		t.Fatalf("status: %d", rec.Code)
	}
}
