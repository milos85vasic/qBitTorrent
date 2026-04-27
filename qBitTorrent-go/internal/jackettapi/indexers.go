package jackettapi

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/db/repos"
	"github.com/milos85vasic/qBitTorrent-go/internal/jackett"
)

// IndexersDeps wires the runtime deps the indexers endpoints need (spec
// §8.2). Indexers/Creds/Catalog point at the Phase-1 repo types; Jackett
// is the admin-API client used to push templates and probe indexers.
//
// In tests, Catalog may be empty (lookup returns ErrNotFound) and the
// handler falls back to id-as-display + "" type — operators refresh the
// catalog separately via Task 18.
type IndexersDeps struct {
	Indexers *repos.Indexers
	Creds    *repos.Credentials
	Catalog  *repos.Catalog
	Jackett  *jackett.Client
}

// indexerDTO is the spec §8.2 GET / POST / PATCH response shape. All
// nullable columns map to *time.Time / *string so JSON marshals to null
// rather than zero values.
type indexerDTO struct {
	ID                   string     `json:"id"`
	DisplayName          string     `json:"display_name"`
	Type                 string     `json:"type"`
	ConfiguredAtJackett  bool       `json:"configured_at_jackett"`
	LinkedCredentialName *string    `json:"linked_credential_name"`
	EnabledForSearch     bool       `json:"enabled_for_search"`
	LastJackettSyncAt    *time.Time `json:"last_jackett_sync_at"`
	LastTestStatus       *string    `json:"last_test_status"`
	LastTestAt           *time.Time `json:"last_test_at"`
}

func indexerToDTO(i *repos.Indexer) indexerDTO {
	return indexerDTO{
		ID:                   i.ID,
		DisplayName:          i.DisplayName,
		Type:                 i.Type,
		ConfiguredAtJackett:  i.ConfiguredAtJackett,
		LinkedCredentialName: i.LinkedCredentialName,
		EnabledForSearch:     i.EnabledForSearch,
		LastJackettSyncAt:    i.LastJackettSyncAt,
		LastTestStatus:       i.LastTestStatus,
		LastTestAt:           i.LastTestAt,
	}
}

// indexerConfigureBody is the POST /indexers/{id} request body per spec §8.2.
// CredentialName names a row in the credentials table; ExtraFields lets the
// caller override or supplement specific template fields by id (matching
// id wins over the credential-derived value).
type indexerConfigureBody struct {
	CredentialName string           `json:"credential_name"`
	ExtraFields    []map[string]any `json:"extra_fields,omitempty"`
}

// indexerPatchBody is the PATCH /indexers/{id} request body. Only
// EnabledForSearch is currently a togglable field (spec §8.2).
type indexerPatchBody struct {
	EnabledForSearch *bool `json:"enabled_for_search,omitempty"`
}

// indexerTestResult is the POST /indexers/{id}/test response per spec §8.2.
type indexerTestResult struct {
	Status  string `json:"status"`
	Details string `json:"details,omitempty"`
}

// HandleListIndexers handles GET /indexers per spec §8.2 — returns a JSON
// array of [indexerDTO]. Empty list serializes as `[]`.
func (d *IndexersDeps) HandleListIndexers(w http.ResponseWriter, r *http.Request) {
	rows, err := d.Indexers.List()
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, "list_failed", err.Error())
		return
	}
	out := make([]indexerDTO, 0, len(rows))
	for _, i := range rows {
		out = append(out, indexerToDTO(i))
	}
	writeJSON(w, http.StatusOK, out)
}

// HandleConfigureIndexer handles POST /indexers/{id} per spec §8.2:
//
//  1. Path id parsed from URL; nested segments (e.g. /id/extra) → 400.
//  2. Body decoded; missing credential_name → 400.
//  3. Credential decrypted; missing → 404.
//  4. Jackett indexer template fetched; failure → 502 template_fetch_failed.
//  5. [jackett.FillFields] populates known credential fields. If zero
//     fields filled (e.g. cookie-only template + userpass cred) → 400
//     no_compatible_credential_fields_for_indexer.
//  6. ExtraFields entries with matching `id` override the populated
//     template's `value` (later wins). Documented merge semantics:
//     extra-fields ALWAYS override template-derived values.
//  7. Posted to Jackett; failure → 502 jackett_post_failed.
//  8. Catalog lookup is best-effort: on hit, display_name + type are
//     copied from the catalog entry; on miss, id is used as display_name
//     and type is left empty.
//  9. Indexer row upserted with configured_at_jackett=true,
//     enabled_for_search=true, linked_credential_name=<cred>,
//     last_jackett_sync_at=now.
//  10. Response is the just-built row as a [indexerDTO] (no DB re-read —
//     we just wrote it).
func (d *IndexersDeps) HandleConfigureIndexer(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/api/v1/jackett/indexers/")
	if id == "" || strings.Contains(id, "/") {
		writeJSONError(w, http.StatusBadRequest, "bad_id", "id path segment required")
		return
	}

	var body indexerConfigureBody
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeJSONError(w, http.StatusBadRequest, "bad_json", err.Error())
		return
	}
	if body.CredentialName == "" {
		writeJSONError(w, http.StatusBadRequest, "missing_credential_name", "credential_name is required")
		return
	}

	cred, err := d.Creds.Get(body.CredentialName)
	if err != nil {
		if errors.Is(err, repos.ErrNotFound) {
			writeJSONError(w, http.StatusNotFound, "credential_not_found", body.CredentialName)
			return
		}
		writeJSONError(w, http.StatusInternalServerError, "credential_get_failed", err.Error())
		return
	}

	template, err := d.Jackett.GetIndexerTemplate(id)
	if err != nil {
		writeJSONError(w, http.StatusBadGateway, "template_fetch_failed", err.Error())
		return
	}

	populated, filled := jackett.FillFields(template, cred)
	if filled == 0 {
		writeJSONError(w, http.StatusBadRequest, "no_compatible_credential_fields_for_indexer",
			"credential kind does not match any template field")
		return
	}

	// extra_fields: override matching ids in the populated template.
	if len(body.ExtraFields) > 0 {
		populated = mergeExtraFields(populated, body.ExtraFields)
	}

	if err := d.Jackett.PostIndexerConfig(id, populated); err != nil {
		writeJSONError(w, http.StatusBadGateway, "jackett_post_failed", err.Error())
		return
	}

	// Catalog lookup is best-effort.
	displayName, typ := id, ""
	if d.Catalog != nil {
		if entry, cerr := d.Catalog.Get(id); cerr == nil {
			if entry.DisplayName != "" {
				displayName = entry.DisplayName
			}
			typ = entry.Type
		}
	}

	credName := body.CredentialName
	now := time.Now().UTC()
	row := &repos.Indexer{
		ID:                   id,
		DisplayName:          displayName,
		Type:                 typ,
		ConfiguredAtJackett:  true,
		LinkedCredentialName: &credName,
		EnabledForSearch:     true,
		LastJackettSyncAt:    &now,
	}
	if err := d.Indexers.Upsert(row); err != nil {
		writeJSONError(w, http.StatusInternalServerError, "db_upsert_failed", err.Error())
		return
	}

	writeJSON(w, http.StatusOK, indexerToDTO(row))
}

// HandleDeleteIndexer handles DELETE /indexers/{id} per spec §8.2: removes
// from Jackett (best-effort) AND from the local DB. Returns 204 even when
// the Jackett-side delete fails — the DB is canonical for our state, and
// the operator's intent is "the row goes away regardless".
func (d *IndexersDeps) HandleDeleteIndexer(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/api/v1/jackett/indexers/")
	if id == "" || strings.Contains(id, "/") {
		writeJSONError(w, http.StatusBadRequest, "bad_id", "id path segment required")
		return
	}

	if d.Jackett != nil {
		if err := d.Jackett.DeleteIndexer(id); err != nil {
			log.Printf("indexers: Jackett DeleteIndexer(%s) failed (continuing): %v", id, err)
		}
	}

	if err := d.Indexers.Delete(id); err != nil {
		writeJSONError(w, http.StatusInternalServerError, "db_delete_failed", err.Error())
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// HandleTestIndexer handles POST /indexers/{id}/test per spec §8.2.
// Path is /api/v1/jackett/indexers/{id}/test.
//
// Implementation note (DONE_WITH_CONCERNS): this is the MINIMAL test —
// it probes the indexer's /config endpoint via [jackett.Client.TestIndexer]
// rather than running a real torznab search query. The "empty_results"
// status from the spec enum is therefore not currently produced; the
// torznab search path lives in a follow-up task wiring search through
// this client. Mapping today:
//
//   - HTTP 200 → "ok"
//   - HTTP 401 → "auth_failed"
//   - transport/network failure → "unreachable"
//   - any other 4xx/5xx → "unreachable" (treated as a generic probe failure)
//
// Side-effect: writes last_test_status + last_test_at via
// [repos.Indexers.RecordTest]. ErrNotFound on RecordTest is logged but
// not surfaced — the operator might be testing an indexer that hasn't
// been configured-then-imported yet.
func (d *IndexersDeps) HandleTestIndexer(w http.ResponseWriter, r *http.Request) {
	rest := strings.TrimPrefix(r.URL.Path, "/api/v1/jackett/indexers/")
	id := strings.TrimSuffix(rest, "/test")
	if id == "" || strings.Contains(id, "/") || id == rest {
		writeJSONError(w, http.StatusBadRequest, "bad_id", "id path segment required")
		return
	}

	result := indexerTestResult{Status: "ok"}
	if err := d.Jackett.TestIndexer(id); err != nil {
		switch err.Error() {
		case "auth_failed":
			result.Status = "auth_failed"
		case "unreachable":
			result.Status = "unreachable"
		default:
			result.Status = "unreachable"
			result.Details = err.Error()
		}
	}

	if rerr := d.Indexers.RecordTest(id, result.Status); rerr != nil && !errors.Is(rerr, repos.ErrNotFound) {
		log.Printf("indexers: RecordTest(%s,%s) failed: %v", id, result.Status, rerr)
	}

	writeJSON(w, http.StatusOK, result)
}

// HandlePatchIndexer handles PATCH /indexers/{id} per spec §8.2. The only
// togglable field today is EnabledForSearch. Body without that field → 400.
func (d *IndexersDeps) HandlePatchIndexer(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/api/v1/jackett/indexers/")
	if id == "" || strings.Contains(id, "/") {
		writeJSONError(w, http.StatusBadRequest, "bad_id", "id path segment required")
		return
	}

	var body indexerPatchBody
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeJSONError(w, http.StatusBadRequest, "bad_json", err.Error())
		return
	}
	if body.EnabledForSearch == nil {
		writeJSONError(w, http.StatusBadRequest, "no_fields", "enabled_for_search is required")
		return
	}

	if err := d.Indexers.SetEnabled(id, *body.EnabledForSearch); err != nil {
		if errors.Is(err, repos.ErrNotFound) {
			writeJSONError(w, http.StatusNotFound, "indexer_not_found", id)
			return
		}
		writeJSONError(w, http.StatusInternalServerError, "db_update_failed", err.Error())
		return
	}

	row, err := d.Indexers.Get(id)
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, "post_write_read_failed", err.Error())
		return
	}
	writeJSON(w, http.StatusOK, indexerToDTO(row))
}

// mergeExtraFields overrides each populated-template field with the
// matching-id entry from extras (later wins). Fields in extras that have no
// matching id in the template are appended at the end so an operator can
// add a non-template field if Jackett accepts it.
func mergeExtraFields(populated, extras []map[string]any) []map[string]any {
	if len(extras) == 0 {
		return populated
	}
	// Build an id→index map for O(N+M) merging.
	idx := make(map[string]int, len(populated))
	for i, f := range populated {
		if id, ok := f["id"].(string); ok {
			idx[id] = i
		}
	}
	for _, ex := range extras {
		eid, ok := ex["id"].(string)
		if !ok {
			continue
		}
		if i, present := idx[eid]; present {
			// Override the value (and any other keys the caller specified).
			for k, v := range ex {
				populated[i][k] = v
			}
			continue
		}
		// Append unknown id verbatim.
		populated = append(populated, ex)
	}
	return populated
}
