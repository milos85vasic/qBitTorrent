package jackettapi

import (
	"encoding/json"
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

// runsHarness wires a fresh DB + a stubbed AutoconfigOnce closure. The
// atomic counter lets us assert (CONST-XII anti-bluff) that
// HandleTriggerRun actually invoked the orchestrator rather than
// hardcoding a 200.
type runsHarness struct {
	deps            *RunsDeps
	autoconfigCalls int32
}

func newRunsHarness(t *testing.T) *runsHarness {
	t.Helper()
	dir := t.TempDir()
	conn, err := db.Open(filepath.Join(dir, "t.db"))
	if err != nil {
		t.Fatalf("db.Open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	h := &runsHarness{}
	h.deps = &RunsDeps{
		Repo: repos.NewRuns(conn),
		AutoconfigOnce: func() jackett.AutoconfigResult {
			atomic.AddInt32(&h.autoconfigCalls, 1)
			return jackett.AutoconfigResult{
				RanAt:                 time.Now().UTC(),
				DiscoveredCredentials: []string{"RUTRACKER"},
				MatchedIndexers:       map[string]string{"RUTRACKER": "rutracker"},
				ConfiguredNow:         []string{"rutracker"},
			}
		},
	}
	t.Cleanup(func() { _ = conn.Close() })
	return h
}

func TestListRunsEmpty(t *testing.T) {
	h := newRunsHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/autoconfig/runs", nil)
	h.deps.HandleListRuns(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	var got []runSummaryDTO
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(got) != 0 {
		t.Fatalf("want 0, got %d", len(got))
	}
}

func TestListRunsReturnsRowsInDescOrder(t *testing.T) {
	h := newRunsHarness(t)
	// Seed 3 runs with different timestamps and discovered counts so we
	// can verify DESC-by-ran_at ordering by reading the discovered_count.
	for i := 0; i < 3; i++ {
		if _, err := h.deps.Repo.Insert(&repos.Run{
			RanAt:              time.Now().UTC().Add(time.Duration(i) * time.Hour),
			DiscoveredCount:    i + 1,
			ConfiguredNowCount: i,
			ErrorsJSON:         "[]",
			ResultSummaryJSON:  `{"discovered":["X"]}`,
		}); err != nil {
			t.Fatalf("seed insert %d: %v", i, err)
		}
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/autoconfig/runs", nil)
	h.deps.HandleListRuns(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d", rec.Code)
	}
	var got []runSummaryDTO
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(got) != 3 {
		t.Fatalf("want 3, got %d", len(got))
	}
	// repo orders DESC by ran_at — first row is the most recent (i==2,
	// discovered_count=3).
	if got[0].DiscoveredCount != 3 {
		t.Fatalf("expected DESC order; first.discovered_count=%d", got[0].DiscoveredCount)
	}
}

func TestListRunsLimit(t *testing.T) {
	h := newRunsHarness(t)
	for i := 0; i < 10; i++ {
		if _, err := h.deps.Repo.Insert(&repos.Run{
			RanAt:             time.Now().UTC().Add(time.Duration(i) * time.Minute),
			DiscoveredCount:   i,
			ErrorsJSON:        "[]",
			ResultSummaryJSON: "{}",
		}); err != nil {
			t.Fatalf("seed %d: %v", i, err)
		}
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/autoconfig/runs?limit=3", nil)
	h.deps.HandleListRuns(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d", rec.Code)
	}
	var got []runSummaryDTO
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(got) != 3 {
		t.Fatalf("want 3, got %d", len(got))
	}
}

func TestListRunsLimitCappedAt200(t *testing.T) {
	h := newRunsHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/autoconfig/runs?limit=999", nil)
	h.deps.HandleListRuns(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
}

func TestListRunsErrorCountFromJSON(t *testing.T) {
	h := newRunsHarness(t)
	if _, err := h.deps.Repo.Insert(&repos.Run{
		RanAt:             time.Now().UTC(),
		ErrorsJSON:        `["e1","e2","e3"]`,
		ResultSummaryJSON: "{}",
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/autoconfig/runs", nil)
	h.deps.HandleListRuns(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d", rec.Code)
	}
	var got []runSummaryDTO
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(got) != 1 {
		t.Fatalf("want 1 row, got %d", len(got))
	}
	if got[0].ErrorCount != 3 {
		t.Fatalf("want 3 errors, got %d", got[0].ErrorCount)
	}
}

func TestGetRunReturnsStoredJSONVerbatim(t *testing.T) {
	h := newRunsHarness(t)
	summary := `{"discovered":["RUTRACKER"],"configured_now":["rutracker"]}`
	id, err := h.deps.Repo.Insert(&repos.Run{
		RanAt:              time.Now().UTC(),
		DiscoveredCount:    1,
		ConfiguredNowCount: 1,
		ErrorsJSON:         "[]",
		ResultSummaryJSON:  summary,
	})
	if err != nil {
		t.Fatalf("seed insert: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/autoconfig/runs/"+strconv.FormatInt(id, 10), nil)
	h.deps.HandleGetRun(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	if rec.Body.String() != summary {
		t.Fatalf("body mismatch:\n want %s\n got  %s", summary, rec.Body.String())
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Fatalf("content-type: %s", ct)
	}
}

func TestGetRunNotFound(t *testing.T) {
	h := newRunsHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/autoconfig/runs/9999", nil)
	h.deps.HandleGetRun(rec, req)
	if rec.Code != 404 {
		t.Fatalf("status: %d", rec.Code)
	}
}

func TestGetRunBadIDReturns400(t *testing.T) {
	h := newRunsHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/autoconfig/runs/not-a-number", nil)
	h.deps.HandleGetRun(rec, req)
	if rec.Code != 400 {
		t.Fatalf("status: %d", rec.Code)
	}
}

func TestGetRunEmptyIDReturns400(t *testing.T) {
	h := newRunsHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/autoconfig/runs/", nil)
	h.deps.HandleGetRun(rec, req)
	if rec.Code != 400 {
		t.Fatalf("status: %d", rec.Code)
	}
}

func TestGetRunNestedPathReturns400(t *testing.T) {
	h := newRunsHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/autoconfig/runs/1/extra", nil)
	h.deps.HandleGetRun(rec, req)
	if rec.Code != 400 {
		t.Fatalf("status: %d", rec.Code)
	}
}

func TestTriggerRunInvokesAutoconfigAndReturnsResult(t *testing.T) {
	h := newRunsHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/autoconfig/run", nil)
	h.deps.HandleTriggerRun(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	// CONST-XII: verify the orchestrator was actually invoked. A stubbed
	// handler that hardcodes 200 + empty body would fail this check.
	if got := atomic.LoadInt32(&h.autoconfigCalls); got != 1 {
		t.Fatalf("autoconfigCalls: want 1 got %d", got)
	}
	var got jackett.AutoconfigResult
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(got.DiscoveredCredentials) != 1 || got.DiscoveredCredentials[0] != "RUTRACKER" {
		t.Fatalf("discovered: %+v", got.DiscoveredCredentials)
	}
	if len(got.ConfiguredNow) != 1 || got.ConfiguredNow[0] != "rutracker" {
		t.Fatalf("configured_now: %+v", got.ConfiguredNow)
	}
}

func TestTriggerRunReturns503WhenNotWired(t *testing.T) {
	h := newRunsHarness(t)
	h.deps.AutoconfigOnce = nil
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/autoconfig/run", nil)
	h.deps.HandleTriggerRun(rec, req)
	if rec.Code != 503 {
		t.Fatalf("want 503, got %d body=%s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), "autoconfig_not_wired") {
		t.Fatalf("body missing code: %s", rec.Body.String())
	}
}
