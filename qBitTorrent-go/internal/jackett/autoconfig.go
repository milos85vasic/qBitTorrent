package jackett

import (
	"encoding/json"
	"fmt"
	"log"
	"sort"
	"strings"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/db/repos"
)

// AutoconfigResult mirrors the Python AutoconfigResult shape so the merge
// service / dashboard can consume the same JSON payload regardless of which
// backend (Python or Go) ran the autoconfig pass.
//
// JSON tags use snake_case for parity with the Python pydantic model. The
// `discovered` key matches the Python `Field(alias="discovered")` on
// `discovered_credentials` — keep this exact tag so existing dashboard
// consumers don't break.
type AutoconfigResult struct {
	RanAt                 time.Time         `json:"ran_at"`
	DiscoveredCredentials []string          `json:"discovered"`
	MatchedIndexers       map[string]string `json:"matched_indexers"`
	ConfiguredNow         []string          `json:"configured_now"`
	AlreadyPresent        []string          `json:"already_present"`
	SkippedNoMatch        []string          `json:"skipped_no_match"`
	SkippedAmbiguous      []AmbiguousMatch  `json:"skipped_ambiguous"`
	// ServedByNativePlugin lists names from SkippedNoMatch (or
	// DiscoveredCredentials) that are known to be served by a native
	// qBittorrent plugin (e.g. NNMCLUB) instead of Jackett. The dashboard
	// uses this to render a "this is fine" banner instead of an error,
	// since the user does not need to wire up a Jackett indexer for these.
	// See plan §32 (NNMClub clarification).
	ServedByNativePlugin []string `json:"served_by_native_plugin"`
	Errors               []string `json:"errors"`
}

// nativePluginNames lists tracker env-var prefixes that are served by a
// native qBittorrent plugin in plugins/ instead of Jackett. Membership is
// upper-case to match the env-var prefix convention. Extend as needed.
var nativePluginNames = map[string]bool{
	"NNMCLUB": true,
}

// classifyServedByNativePlugin returns the subset of the given names that
// match the native-plugin allowlist. Used to populate
// AutoconfigResult.ServedByNativePlugin from the unmatched/discovered
// pools so the UI can show a clarifying banner.
func classifyServedByNativePlugin(names []string) []string {
	out := make([]string, 0)
	for _, n := range names {
		if nativePluginNames[strings.ToUpper(n)] {
			out = append(out, n)
		}
	}
	sort.Strings(out)
	return out
}

// AutoconfigDeps holds the DB repositories and the Jackett client the
// orchestrator wires together. The runtime constructs it once at boot
// and reuses across triggers.
type AutoconfigDeps struct {
	Creds     *repos.Credentials
	Overrides *repos.Overrides
	Indexers  *repos.Indexers
	Runs      *repos.Runs
	Client    *Client
}

// ParseIndexerMapCSV parses "NAME:id,NAME2:id2" CSV into an override map.
// Keys are uppercased; values left as-is. Empty / malformed pairs skipped.
// Returns an empty (non-nil) map when input is empty so callers can merge
// without nil checks. Mirrors Python _parse_indexer_map.
func ParseIndexerMapCSV(raw string) map[string]string {
	out := map[string]string{}
	if raw == "" {
		return out
	}
	for _, pair := range strings.Split(raw, ",") {
		pair = strings.TrimSpace(pair)
		if pair == "" || !strings.Contains(pair, ":") {
			continue
		}
		idx := strings.IndexByte(pair, ':')
		k := strings.TrimSpace(strings.ToUpper(pair[:idx]))
		v := strings.TrimSpace(pair[idx+1:])
		if k != "" && v != "" {
			out[k] = v
		}
	}
	return out
}

// FillFields walks a Jackett indexer config template, populates known
// credential keys ("username", "password", "cookie"/"cookies"/"cookieheader")
// from the bundle, returns the populated template AND a count of fields filled.
//
// Returns count==0 when none of the template's id keys match a credential
// the bundle actually has — caller treats that as
// no_compatible_credential_fields_for_indexer (e.g. iptorrents needs cookie
// but the bundle is userpass-only).
//
// Exported for use by [internal/jackettapi.HandleConfigureIndexer]; the
// helper has no internal state, so a public function is the cleanest seam.
func FillFields(template []map[string]any, cred *repos.Credential) ([]map[string]any, int) {
	fieldMap := map[string]string{
		"username":     cred.Username,
		"password":     cred.Password,
		"cookie":       cred.Cookies,
		"cookies":      cred.Cookies,
		"cookieheader": cred.Cookies,
	}
	populated := make([]map[string]any, 0, len(template))
	filled := 0
	for _, f := range template {
		// Shallow-copy: Jackett field values are scalars, no nested maps
		// we need to deep-copy. Caller still gets independent maps.
		nf := make(map[string]any, len(f))
		for k, v := range f {
			nf[k] = v
		}
		if id, ok := nf["id"].(string); ok {
			if val, present := fieldMap[id]; present && val != "" {
				nf["value"] = val
				filled++
			}
		}
		populated = append(populated, nf)
	}
	return populated, filled
}

// Autoconfigure runs one full autoconfig pass:
//
//  1. snapshot credentials + overrides from DB
//  2. merge envOverrides (e.g. JACKETT_INDEXER_MAP CSV) into the override map
//     — DB wins on key collision (DB is canonical, env is a legacy migration
//     helper)
//  3. WarmUp + GetCatalog
//  4. MatchIndexers
//  5. for each match: GetIndexerTemplate → FillFields → PostIndexerConfig
//     → Indexers.Upsert + Credentials.MarkUsed
//  6. Runs.Insert with a summary
//  7. return AutoconfigResult
//
// Never panics; all errors land in result.Errors. The orchestrator is
// idempotent: matched indexers already configured at Jackett are recorded
// in AlreadyPresent without a re-POST.
//
// envOverrides is the parsed JACKETT_INDEXER_MAP. Pass nil or empty to skip
// env merge entirely.
func Autoconfigure(deps AutoconfigDeps, envOverrides map[string]string) AutoconfigResult {
	started := time.Now().UTC()
	// Pre-allocate every slice/map field as non-nil so JSON serializes
	// `[]` / `{}` instead of `null`. The OpenAPI contract requires these
	// fields to be non-nullable arrays/objects (spec §8.4 +
	// internal/jackettapi/openapi.json AutoconfigResult). nil slices in
	// Go marshal to `null`, breaking the contract.
	result := AutoconfigResult{
		RanAt:                 started,
		DiscoveredCredentials: []string{},
		MatchedIndexers:       map[string]string{},
		ConfiguredNow:         []string{},
		AlreadyPresent:        []string{},
		SkippedNoMatch:        []string{},
		SkippedAmbiguous:      []AmbiguousMatch{},
		ServedByNativePlugin:  []string{},
		Errors:                []string{},
	}

	// Step 1: load credentials metadata, then decrypt only the rows that
	// actually carry a usable secret. We sort the kept names alphabetically
	// for deterministic discovered/matched output.
	bundles, discovered, listErr := loadBundles(deps.Creds)
	if listErr != nil {
		result.Errors = append(result.Errors, fmt.Sprintf("credentials_list_failed: %v", listErr))
		recordRun(deps.Runs, &result, started, 0)
		return result
	}
	result.DiscoveredCredentials = discovered

	// Pre-populate ServedByNativePlugin from `discovered` BEFORE any
	// early-exit path. If the operator has e.g. NNMCLUB credentials, the
	// dashboard banner must render even when Jackett is unreachable —
	// otherwise the user thinks "Boba is broken" when really NNMCLUB is
	// served by the native plugin and the unrelated Jackett-down state
	// is just orthogonal noise. The success path further down REMOVES
	// names that did get matched + configured at Jackett (since in that
	// case Jackett DOES handle them and the banner would mislead).
	// Caught by challenges/scripts/nnmclub_native_plugin_clarification_challenge.sh
	// which runs against an unreachable Jackett and asserts NNMCLUB
	// still appears in served_by_native_plugin.
	{
		preNative := classifyServedByNativePlugin(discovered)
		sort.Strings(preNative)
		result.ServedByNativePlugin = preNative
	}

	if len(bundles) == 0 {
		recordRun(deps.Runs, &result, started, 0)
		return result
	}

	if deps.Client == nil || deps.Client.apiKey == "" {
		result.Errors = append(result.Errors, "jackett_auth_missing_key")
		recordRun(deps.Runs, &result, started, len(bundles))
		return result
	}

	// Step 2: merge env-derived overrides with DB overrides; DB wins on key
	// collision so operator UI edits override stale env values.
	override := map[string]string{}
	for k, v := range envOverrides {
		override[k] = v
	}
	if dbMap, err := deps.Overrides.AsMap(); err == nil {
		for k, v := range dbMap {
			override[k] = v
		}
	} else {
		result.Errors = append(result.Errors, fmt.Sprintf("overrides_load_failed: %v", err))
	}

	// Step 3: warm session, fetch catalog. WarmUp failure is tolerated per
	// Python — a real auth problem will surface on the catalog GET.
	_ = deps.Client.WarmUp()
	catalog, err := deps.Client.GetCatalog()
	if err != nil {
		// Map known sentinel errors verbatim (jackett_auth_failed,
		// jackett_catalog_http_NNN). Anything else gets routed to
		// jackett_unreachable for parity with Python.
		msg := err.Error()
		if strings.HasPrefix(msg, "jackett_") {
			result.Errors = append(result.Errors, msg)
		} else {
			result.Errors = append(result.Errors, "jackett_unreachable")
		}
		recordRun(deps.Runs, &result, started, len(bundles))
		return result
	}

	already := map[string]bool{}
	for _, e := range catalog {
		if e.Configured {
			already[e.ID] = true
		}
	}

	// Step 4: match. envNames must be the sorted bundle names so matched
	// iteration order downstream stays deterministic.
	matched, ambiguous, unmatched := MatchIndexers(discovered, catalog, override)
	// Preserve non-nil empties when MatchIndexers returns nil (no matches /
	// no ambiguities / no unmatched) so the JSON contract stays
	// `[]` / `{}`, not `null`. See AutoconfigResult init at top of fn.
	if matched == nil {
		matched = map[string]string{}
	}
	if ambiguous == nil {
		ambiguous = []AmbiguousMatch{}
	}
	if unmatched == nil {
		unmatched = []string{}
	}
	result.MatchedIndexers = matched
	result.SkippedAmbiguous = ambiguous
	result.SkippedNoMatch = unmatched

	// Tag any unmatched names that are actually served by a native
	// qBittorrent plugin (e.g. NNMCLUB) so the UI can render a clarifying
	// banner instead of treating it as a bug. We also scan ambiguous
	// candidates and the full discovered list — if a known native plugin
	// shows up anywhere in these pools, the user gets the banner.
	nativeSet := map[string]bool{}
	for _, n := range classifyServedByNativePlugin(unmatched) {
		nativeSet[n] = true
	}
	for _, a := range ambiguous {
		for _, n := range classifyServedByNativePlugin([]string{a.EnvName}) {
			nativeSet[n] = true
		}
	}
	for _, n := range classifyServedByNativePlugin(discovered) {
		// Only flag if it's NOT already happily configured at Jackett —
		// that would mean Jackett DOES support it for this user.
		if _, ok := matched[n]; !ok {
			nativeSet[n] = true
		}
	}
	served := make([]string, 0, len(nativeSet))
	for n := range nativeSet {
		served = append(served, n)
	}
	sort.Strings(served)
	result.ServedByNativePlugin = served

	// Step 5: configure. Iterate matched in env-name order for determinism
	// (map range is unordered).
	envNames := make([]string, 0, len(matched))
	for k := range matched {
		envNames = append(envNames, k)
	}
	sort.Strings(envNames)

	for _, envName := range envNames {
		indexerID := matched[envName]
		// Mirror catalog state (display_name, type) into our DB regardless
		// of whether we re-POST or not — the indexers table is meant as a
		// snapshot of "what's wired up at Jackett".
		entry := findCatalog(catalog, indexerID)

		if already[indexerID] {
			result.AlreadyPresent = append(result.AlreadyPresent, indexerID)
			upsertIndexerRow(deps.Indexers, entry, indexerID, envName, started)
			// Don't MarkUsed — we didn't actually consume credentials this run.
			continue
		}

		if errMsg := configureOne(deps, envName, indexerID, bundles[envName]); errMsg != "" {
			result.Errors = append(result.Errors, fmt.Sprintf("indexer_config_failed:%s:%s", indexerID, errMsg))
			continue
		}
		result.ConfiguredNow = append(result.ConfiguredNow, indexerID)
		upsertIndexerRow(deps.Indexers, entry, indexerID, envName, started)
		// Best-effort — log but do not surface. The Task 14 redactor will
		// scrub if a leak ever sneaks in.
		if mErr := deps.Creds.MarkUsed(envName); mErr != nil {
			log.Printf("autoconfig: MarkUsed(%s) failed: %v", envName, mErr)
		}
	}

	recordRun(deps.Runs, &result, started, len(bundles))
	return result
}

// configureOne handles the per-indexer happy-path: GET template, fill
// fields, POST. Returns "" on success, an error string (without the
// "indexer_config_failed:<id>:" prefix — caller adds it) on failure.
//
// Mirrors Python _configure_one: one retry on a 5xx after a 2-second
// sleep, then surface the failure.
//
// NOTE: Client.PostIndexerConfig always sends bare-list. The Python
// helper preserves the GET envelope shape ({"config": ...} vs bare-list).
// Real Jackett accepts both for every indexer in our shipped catalog,
// confirmed by Layer 3 E2E and Layer 7 challenge runs (see
// challenges/scripts/boba_jackett_autoconfig_challenge.sh). If a strict
// indexer surfaces in the wild, parameterise PostIndexerConfig to mirror
// the shape returned by GetIndexerTemplate.
func configureOne(deps AutoconfigDeps, envName, indexerID string, cred *repos.Credential) string {
	tmpl, err := deps.Client.GetIndexerTemplate(indexerID)
	if err != nil {
		return err.Error()
	}
	populated, filled := FillFields(tmpl, cred)
	if filled == 0 {
		return "no_compatible_credential_fields_for_indexer"
	}
	if err := deps.Client.PostIndexerConfig(indexerID, populated); err != nil {
		// Retry once on 5xx with a 2-second backoff. The error string from
		// PostIndexerConfig is "config POST HTTP <code>" — we sniff the
		// numeric code by prefix.
		if isServerError(err.Error()) {
			time.Sleep(2 * time.Second)
			if err2 := deps.Client.PostIndexerConfig(indexerID, populated); err2 == nil {
				return ""
			} else {
				return err2.Error()
			}
		}
		return err.Error()
	}
	return ""
}

// isServerError returns true when the PostIndexerConfig error string maps
// to a 5xx HTTP status.
func isServerError(msg string) bool {
	const prefix = "config POST HTTP "
	if !strings.HasPrefix(msg, prefix) {
		return false
	}
	rest := strings.TrimPrefix(msg, prefix)
	return strings.HasPrefix(rest, "5")
}

// loadBundles returns a name→Credential map of bundles that carry usable
// secrets, plus the sorted list of names. Rows with no userpass pair AND
// no cookies are skipped (they couldn't satisfy any indexer template).
func loadBundles(c *repos.Credentials) (map[string]*repos.Credential, []string, error) {
	rows, err := c.List()
	if err != nil {
		return nil, nil, err
	}
	keep := []string{}
	for _, r := range rows {
		if !((r.HasUsername && r.HasPassword) || r.HasCookies) {
			continue
		}
		keep = append(keep, r.Name)
	}
	sort.Strings(keep)
	bundles := make(map[string]*repos.Credential, len(keep))
	for _, name := range keep {
		full, err := c.Get(name)
		if err != nil {
			// Skip (don't fail the whole run) — a single corrupt row
			// shouldn't poison the batch. The error surfaces nowhere
			// because we already counted it in `keep`; remove from final
			// discovered list.
			continue
		}
		bundles[name] = full
	}
	// Rebuild sorted list to match what survived decrypt.
	final := make([]string, 0, len(bundles))
	for k := range bundles {
		final = append(final, k)
	}
	sort.Strings(final)
	return bundles, final, nil
}

// findCatalog returns the catalog entry matching id, or a zero-value entry
// with the id pre-filled (so DB upsert still has a primary key to write).
func findCatalog(catalog []CatalogEntry, id string) CatalogEntry {
	for _, e := range catalog {
		if e.ID == id {
			return e
		}
	}
	return CatalogEntry{ID: id}
}

// upsertIndexerRow mirrors the catalog state into the indexers table. Best
// effort — failure is logged but does not poison the run result.
func upsertIndexerRow(r *repos.Indexers, entry CatalogEntry, id, envName string, syncAt time.Time) {
	linked := envName
	row := &repos.Indexer{
		ID:                   id,
		DisplayName:          entry.Name,
		Type:                 entry.Type,
		ConfiguredAtJackett:  true,
		LinkedCredentialName: &linked,
		EnabledForSearch:     true,
		LastJackettSyncAt:    &syncAt,
	}
	if row.DisplayName == "" {
		row.DisplayName = id
	}
	if row.Type == "" {
		row.Type = "private"
	}
	if err := r.Upsert(row); err != nil {
		log.Printf("autoconfig: indexers.Upsert(%s) failed: %v", id, err)
	}
}

// recordRun marshals the result into the autoconfig_runs table. Insert
// failures append a "run_record_failed" entry to result.Errors AFTER the
// JSON snapshot is taken so the caller still sees a complete result; the
// row simply doesn't persist. discovered is passed in (not derived from
// result) because some early-return paths (e.g. credentials_list_failed)
// haven't populated result.DiscoveredCredentials yet.
func recordRun(runs *repos.Runs, result *AutoconfigResult, started time.Time, discovered int) {
	summary, err := json.Marshal(result)
	if err != nil {
		// Should never happen — all fields are JSON-friendly.
		summary = []byte("{}")
	}
	errsJSON, err := json.Marshal(result.Errors)
	if err != nil || len(result.Errors) == 0 {
		errsJSON = []byte("[]")
	}
	run := &repos.Run{
		RanAt:              started,
		DiscoveredCount:    discovered,
		ConfiguredNowCount: len(result.ConfiguredNow),
		ErrorsJSON:         string(errsJSON),
		ResultSummaryJSON:  string(summary),
	}
	if _, insErr := runs.Insert(run); insErr != nil {
		result.Errors = append(result.Errors, fmt.Sprintf("run_record_failed: %v", insErr))
	}
}
