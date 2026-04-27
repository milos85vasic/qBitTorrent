package jackettapi

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"sync"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/db/repos"
	"github.com/milos85vasic/qBitTorrent-go/internal/jackett"
)

// CatalogDeps wires the catalog repo + Jackett admin-API client (spec §8.3).
//
// refreshMu serializes /catalog/refresh requests. Refresh is expensive
// (one HTTP call per indexer template — ~620 calls in production) and
// concurrent invocations would duplicate work and race on the
// transactional ReplaceAll write. CONST-013 prohibits bare
// `sync.Mutex + map/slice` combos for new code; here `refreshMu` does
// NOT guard a shared collection — it serializes the entire HTTP request
// flow against concurrent refreshes. The Catalog repo handles its own
// concurrency for the actual data writes. Bare mutex is correct.
type CatalogDeps struct {
	Catalog *repos.Catalog
	Jackett *jackett.Client

	refreshMu sync.Mutex
}

// catalogItemDTO mirrors the spec §8.3 GET /catalog item shape.
type catalogItemDTO struct {
	ID             string   `json:"id"`
	DisplayName    string   `json:"display_name"`
	Type           string   `json:"type"`
	Language       string   `json:"language,omitempty"`
	Description    string   `json:"description,omitempty"`
	RequiredFields []string `json:"required_fields"`
}

// catalogPageDTO is the GET /catalog response envelope per spec §8.3.
type catalogPageDTO struct {
	Total    int              `json:"total"`
	Page     int              `json:"page"`
	PageSize int              `json:"page_size"`
	Items    []catalogItemDTO `json:"items"`
}

// catalogRefreshResultDTO is the POST /catalog/refresh response shape.
// Errors is the per-indexer error list — non-empty entries do not abort
// the refresh; the operator surfaces them and decides whether to retry.
type catalogRefreshResultDTO struct {
	RefreshedCount int      `json:"refreshed_count"`
	Errors         []string `json:"errors"`
}

// credentialFieldIDs is the set of Jackett template field ids the dashboard
// treats as credential-bearing (spec §8.3 "required_fields"). We expose
// these to the UI so it can prompt the operator with the right inputs.
var credentialFieldIDs = map[string]bool{
	"username":     true,
	"password":     true,
	"cookie":       true,
	"cookies":      true,
	"cookieheader": true,
}

// extractRequiredFields scans a Jackett indexer template (raw JSON) for
// credential-bearing field ids. The template payload is either a JSON
// array of field-objects or an envelope `{"config": [...]}` (Jackett
// returns whichever shape the version chose). Returns the matching ids
// in template order. On parse failure or empty template returns an
// empty slice — never returns an error: the catalog GET should still
// serve cached entries even if one row's TemplateFieldsJSON is malformed.
func extractRequiredFields(templateFieldsJSON string) []string {
	if templateFieldsJSON == "" {
		return []string{}
	}
	var raw any
	if err := json.Unmarshal([]byte(templateFieldsJSON), &raw); err != nil {
		return []string{}
	}
	var fields []any
	switch v := raw.(type) {
	case []any:
		fields = v
	case map[string]any:
		if cfg, ok := v["config"].([]any); ok {
			fields = cfg
		}
	}
	out := make([]string, 0, len(fields))
	for _, f := range fields {
		m, ok := f.(map[string]any)
		if !ok {
			continue
		}
		id, _ := m["id"].(string)
		if id != "" && credentialFieldIDs[id] {
			out = append(out, id)
		}
	}
	return out
}

// HandleListCatalog handles GET /catalog per spec §8.3:
//
//   - Query params: search, type, language (string filters); page (int,
//     default 1, must be >=1); page_size (int, default 50, capped at 200,
//     min 1).
//   - Bad page / page_size → 400 bad_pagination.
//   - Returns 200 [catalogPageDTO]. Items are mapped from the repo rows;
//     RequiredFields is derived per row from TemplateFieldsJSON.
//
// This handler is purely a DB read — it never triggers a refresh. The
// dashboard calls POST /catalog/refresh explicitly when it wants fresh data.
func (d *CatalogDeps) HandleListCatalog(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()

	page := 1
	if s := q.Get("page"); s != "" {
		v, err := strconv.Atoi(s)
		if err != nil || v < 1 {
			writeJSONError(w, http.StatusBadRequest, "bad_pagination", "page must be >= 1")
			return
		}
		page = v
	}

	pageSize := 50
	if s := q.Get("page_size"); s != "" {
		v, err := strconv.Atoi(s)
		if err != nil || v < 1 {
			writeJSONError(w, http.StatusBadRequest, "bad_pagination", "page_size must be >= 1")
			return
		}
		pageSize = v
	}
	if pageSize > 200 {
		pageSize = 200
	}

	cq := repos.CatalogQuery{
		Limit:  pageSize,
		Offset: (page - 1) * pageSize,
	}
	if s := q.Get("search"); s != "" {
		cq.Search = &s
	}
	if s := q.Get("type"); s != "" {
		cq.Type = &s
	}
	if s := q.Get("language"); s != "" {
		cq.Language = &s
	}

	rows, total, err := d.Catalog.Query(cq)
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, "catalog_query_failed", err.Error())
		return
	}

	items := make([]catalogItemDTO, 0, len(rows))
	for _, e := range rows {
		lang := ""
		if e.Language != nil {
			lang = *e.Language
		}
		desc := ""
		if e.Description != nil {
			desc = *e.Description
		}
		items = append(items, catalogItemDTO{
			ID:             e.ID,
			DisplayName:    e.DisplayName,
			Type:           e.Type,
			Language:       lang,
			Description:    desc,
			RequiredFields: extractRequiredFields(e.TemplateFieldsJSON),
		})
	}

	writeJSON(w, http.StatusOK, catalogPageDTO{
		Total:    total,
		Page:     page,
		PageSize: pageSize,
		Items:    items,
	})
}

// HandleRefreshCatalog handles POST /catalog/refresh per spec §8.3:
//
//  1. Serialized via [CatalogDeps.refreshMu] — concurrent calls block.
//  2. WarmUp() the Jackett session (best-effort; logged on failure).
//  3. GetCatalog() — fatal failure returns 502 jackett_catalog_failed
//     (DB is left untouched).
//  4. For each catalog entry, GetIndexerTemplate(id). Per-indexer errors
//     are collected into the result and do NOT abort the refresh.
//  5. The successful entries are written via Catalog.ReplaceAll (single
//     transaction; truncate + bulk insert).
//  6. If zero entries succeeded (all templates failed): we skip the
//     ReplaceAll call (it refuses empty input as a safety guard) and
//     return 200 with refreshed_count=0 + the error list — the operator
//     wants to see the errors.
func (d *CatalogDeps) HandleRefreshCatalog(w http.ResponseWriter, r *http.Request) {
	d.refreshMu.Lock()
	defer d.refreshMu.Unlock()

	if err := d.Jackett.WarmUp(); err != nil {
		log.Printf("catalog refresh: WarmUp failed (continuing): %v", err)
	}

	entries, err := d.Jackett.GetCatalog()
	if err != nil {
		writeJSONError(w, http.StatusBadGateway, "jackett_catalog_failed", err.Error())
		return
	}

	now := time.Now().UTC()
	rows := make([]*repos.CatalogEntry, 0, len(entries))
	errs := make([]string, 0)
	for _, e := range entries {
		template, terr := d.Jackett.GetIndexerTemplate(e.ID)
		if terr != nil {
			errs = append(errs, fmt.Sprintf("indexer_template_failed:%s:%v", e.ID, terr))
			continue
		}
		raw, merr := json.Marshal(template)
		if merr != nil {
			errs = append(errs, fmt.Sprintf("indexer_template_marshal_failed:%s:%v", e.ID, merr))
			continue
		}
		// Catalog list provides language/description as strings; persist
		// only the non-empty values so the JSON omits them on output
		// (catalogItemDTO uses omitempty).
		var lang, desc *string
		if e.Language != "" {
			s := e.Language
			lang = &s
		}
		if e.Description != "" {
			s := e.Description
			desc = &s
		}
		display := e.Name
		if display == "" {
			display = e.ID
		}
		rows = append(rows, &repos.CatalogEntry{
			ID:                 e.ID,
			DisplayName:        display,
			Type:               e.Type,
			Language:           lang,
			Description:        desc,
			TemplateFieldsJSON: string(raw),
			CachedAt:           now,
		})
	}

	if len(rows) > 0 {
		if rerr := d.Catalog.ReplaceAll(rows); rerr != nil {
			writeJSONError(w, http.StatusInternalServerError, "catalog_replace_failed", rerr.Error())
			return
		}
	}

	writeJSON(w, http.StatusOK, catalogRefreshResultDTO{
		RefreshedCount: len(rows),
		Errors:         errs,
	})
}
