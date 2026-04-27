package jackettapi

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/db/repos"
	"github.com/milos85vasic/qBitTorrent-go/internal/jackett"
)

// RunsDeps wires the autoconfig_runs repo plus the orchestrator-trigger
// closure for spec §8.4 endpoints.
//
// AutoconfigOnce runs a single full orchestrator pass synchronously and
// returns the result. Task 21 wires this to a closure capturing the full
// jackett.AutoconfigDeps; tests stub it to a deterministic
// AutoconfigResult. The indirection keeps this package free of the
// orchestrator's transitive dependency graph (avoids import cycles).
type RunsDeps struct {
	Repo           *repos.Runs
	AutoconfigOnce func() jackett.AutoconfigResult
}

// runSummaryDTO is the GET /autoconfig/runs item shape per spec §8.4.
type runSummaryDTO struct {
	ID                 int64     `json:"id"`
	RanAt              time.Time `json:"ran_at"`
	DiscoveredCount    int       `json:"discovered_count"`
	ConfiguredNowCount int       `json:"configured_now_count"`
	ErrorCount         int       `json:"error_count"`
}

// runToSummary projects a stored Run row into the list-item DTO. The
// error_count field is computed from the stored ErrorsJSON array length;
// invalid/empty JSON degrades to 0 (the row is still listable).
func runToSummary(r *repos.Run) runSummaryDTO {
	var errs []any
	if r.ErrorsJSON != "" {
		_ = json.Unmarshal([]byte(r.ErrorsJSON), &errs)
	}
	return runSummaryDTO{
		ID:                 r.ID,
		RanAt:              r.RanAt,
		DiscoveredCount:    r.DiscoveredCount,
		ConfiguredNowCount: r.ConfiguredNowCount,
		ErrorCount:         len(errs),
	}
}

// HandleListRuns handles GET /autoconfig/runs?limit=N per spec §8.4.
//
// limit defaults to 50, has a min of 1 (negative/zero falls back to
// default), and is silently capped at 200. We never 400 on bad limit —
// the UI just gets a reasonable bounded list.
func (d *RunsDeps) HandleListRuns(w http.ResponseWriter, r *http.Request) {
	limit := 50
	if raw := r.URL.Query().Get("limit"); raw != "" {
		if n, err := strconv.Atoi(raw); err == nil && n > 0 {
			limit = n
		}
	}
	if limit > 200 {
		limit = 200
	}

	rows, err := d.Repo.List(limit)
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, "list_failed", err.Error())
		return
	}
	out := make([]runSummaryDTO, 0, len(rows))
	for _, run := range rows {
		out = append(out, runToSummary(run))
	}
	writeJSON(w, http.StatusOK, out)
}

// HandleGetRun handles GET /autoconfig/runs/{id} per spec §8.4.
//
// Returns the stored result_summary_json verbatim — the orchestrator
// already produced a redacted snapshot at write time (Task 13), so this
// endpoint is byte-for-byte transparent. Content-Type is set explicitly
// because we bypass writeJSON to avoid a re-marshal.
func (d *RunsDeps) HandleGetRun(w http.ResponseWriter, r *http.Request) {
	idStr := strings.TrimPrefix(r.URL.Path, "/api/v1/jackett/autoconfig/runs/")
	if idStr == "" || strings.Contains(idStr, "/") {
		writeJSONError(w, http.StatusBadRequest, "bad_id", "id path segment required")
		return
	}
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		writeJSONError(w, http.StatusBadRequest, "bad_id", "id must be an integer")
		return
	}

	row, err := d.Repo.Get(id)
	if err != nil {
		if errors.Is(err, repos.ErrNotFound) {
			writeJSONError(w, http.StatusNotFound, "run_not_found", idStr)
			return
		}
		writeJSONError(w, http.StatusInternalServerError, "run_get_failed", err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(row.ResultSummaryJSON))
}

// HandleTriggerRun handles POST /autoconfig/run per spec §8.4. Synchronous:
// returns the full redacted summary the orchestrator just produced.
//
// The orchestrator inserts its own autoconfig_runs row internally (see
// jackett.recordRun in autoconfig.go), so this handler does NOT call
// Repo.Insert — that would double-record.
func (d *RunsDeps) HandleTriggerRun(w http.ResponseWriter, r *http.Request) {
	if d.AutoconfigOnce == nil {
		writeJSONError(w, http.StatusServiceUnavailable, "autoconfig_not_wired",
			"autoconfig orchestrator is not wired into this build")
		return
	}
	result := d.AutoconfigOnce()
	writeJSON(w, http.StatusOK, result)
}
