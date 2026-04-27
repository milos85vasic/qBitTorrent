// Package jackettapi — overrides handlers (spec §8.5).
//
// Indexer-name overrides let operators force the autoconfig matcher
// to map a credential bundle (e.g. RUTRACKER) to a specific Jackett
// indexer id (e.g. rutracker_v2) instead of relying on the fuzzy
// matcher. Same data the legacy JACKETT_INDEXER_MAP env var carried,
// now persisted in SQLite.
package jackettapi

import (
	"encoding/json"
	"errors"
	"net/http"
	"strings"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/db/repos"
)

// OverridesDeps wires the repo for the override handlers.
type OverridesDeps struct {
	Repo *repos.Overrides
}

// overrideDTO is the JSON shape returned by GET /overrides and the
// successful POST /overrides response. Mirrors spec §8.5 verbatim.
type overrideDTO struct {
	EnvName   string    `json:"env_name"`
	IndexerID string    `json:"indexer_id"`
	CreatedAt time.Time `json:"created_at"`
}

func overrideToDTO(o *repos.Override) overrideDTO {
	return overrideDTO{EnvName: o.EnvName, IndexerID: o.IndexerID, CreatedAt: o.CreatedAt}
}

// overridePostBody is the POST request body. Both fields are required.
// EnvName is normalized to upper-case to match the autoconfig matcher's
// expectation (env-var names are conventionally upper-case).
type overridePostBody struct {
	EnvName   string `json:"env_name"`
	IndexerID string `json:"indexer_id"`
}

// HandleListOverrides handles GET /overrides.
func (d *OverridesDeps) HandleListOverrides(w http.ResponseWriter, _ *http.Request) {
	rows, err := d.Repo.List()
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, "list_failed", err.Error())
		return
	}
	out := make([]overrideDTO, 0, len(rows))
	for _, o := range rows {
		out = append(out, overrideToDTO(o))
	}
	writeJSON(w, http.StatusOK, out)
}

// HandleUpsertOverride handles POST /overrides. Idempotent: re-POSTing
// the same env_name updates the indexer_id mapping.
func (d *OverridesDeps) HandleUpsertOverride(w http.ResponseWriter, r *http.Request) {
	var body overridePostBody
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeJSONError(w, http.StatusBadRequest, "bad_json", err.Error())
		return
	}
	body.EnvName = strings.TrimSpace(strings.ToUpper(body.EnvName))
	body.IndexerID = strings.TrimSpace(body.IndexerID)
	if body.EnvName == "" || body.IndexerID == "" {
		writeJSONError(w, http.StatusBadRequest, "missing_fields",
			"env_name and indexer_id are required")
		return
	}
	if err := d.Repo.Upsert(body.EnvName, body.IndexerID); err != nil {
		writeJSONError(w, http.StatusInternalServerError, "db_upsert_failed", err.Error())
		return
	}
	// Re-read to populate created_at for the response. Repo has no Get;
	// scan the small list and pick the matching row. Override count is
	// expected in the single digits (one per credential bundle).
	rows, err := d.Repo.List()
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, "post_write_read_failed", err.Error())
		return
	}
	for _, o := range rows {
		if o.EnvName == body.EnvName {
			writeJSON(w, http.StatusOK, overrideToDTO(o))
			return
		}
	}
	// Unreachable in practice — we just wrote the row. Defensive 500.
	writeJSONError(w, http.StatusInternalServerError, "row_disappeared",
		"row not found after upsert")
}

// HandleDeleteOverride handles DELETE /overrides/{env_name}. Idempotent —
// deleting a non-existent override returns 204.
func (d *OverridesDeps) HandleDeleteOverride(w http.ResponseWriter, r *http.Request) {
	name := strings.TrimPrefix(r.URL.Path, "/api/v1/jackett/overrides/")
	if name == "" || strings.Contains(name, "/") {
		writeJSONError(w, http.StatusBadRequest, "bad_name",
			"env_name path segment required")
		return
	}
	if err := d.Repo.Delete(name); err != nil && !errors.Is(err, repos.ErrNotFound) {
		writeJSONError(w, http.StatusInternalServerError, "delete_failed", err.Error())
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
