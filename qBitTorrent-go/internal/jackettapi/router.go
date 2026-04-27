package jackettapi

import (
	"net/http"
	"strings"
)

// Deps bundles every dependency the boba-jackett HTTP service needs.
// main.go constructs this once at boot and hands it to NewMux.
//
// All sub-Deps pointers are required for the corresponding endpoints to
// function — NewMux does not nil-check them per request because the
// boot path always sets them. Tests that exercise only one slice of the
// surface may pass nils for the unused fields, with the corresponding
// route returning a runtime error if invoked.
type Deps struct {
	Credentials *CredentialsDeps
	Indexers    *IndexersDeps
	Catalog     *CatalogDeps
	Runs        *RunsDeps
	Overrides   *OverridesDeps
	Health      *HealthDeps
}

// NewMux wires every spec §8 endpoint onto a stdlib http.ServeMux,
// then wraps with WithAuth so non-GET requests require admin/admin
// Basic auth (Task 15). Returns an http.Handler ready to hand to
// http.Server.
//
// Trailing-slash routes (e.g. /credentials/) catch path-suffixed
// requests like DELETE /credentials/RUTRACKER. The handlers themselves
// parse the suffix; the router just dispatches by prefix.
//
// Route table (spec §8):
//
//	/healthz                                    GET            §8.6
//	/openapi.json                               GET            Task 22
//	/api/v1/jackett/credentials                 GET, POST      §8.1
//	/api/v1/jackett/credentials/{name}          DELETE         §8.1
//	/api/v1/jackett/indexers                    GET            §8.2
//	/api/v1/jackett/indexers/{id}               POST,DELETE,PATCH §8.2
//	/api/v1/jackett/indexers/{id}/test          POST           §8.2
//	/api/v1/jackett/catalog                     GET            §8.3
//	/api/v1/jackett/catalog/refresh             POST           §8.3
//	/api/v1/jackett/autoconfig/runs             GET            §8.4
//	/api/v1/jackett/autoconfig/runs/{id}        GET            §8.4
//	/api/v1/jackett/autoconfig/run              POST           §8.4 (trigger)
//	/api/v1/jackett/overrides                   GET, POST      §8.5
//	/api/v1/jackett/overrides/{env_name}        DELETE         §8.5
//
// NOTE: /autoconfig/run (trigger) and /autoconfig/runs (list) share
// the prefix "/autoconfig/run" but are registered as distinct exact
// paths (no trailing slash on either) so stdlib ServeMux matches them
// correctly. /autoconfig/runs/ (with trailing slash) handles the
// GET-by-id case.
func NewMux(d *Deps) http.Handler {
	mux := http.NewServeMux()

	// §8.6 health (GET only — passes WithAuth without credentials).
	mux.HandleFunc("/healthz", d.Health.HandleHealth)

	// Task 22 OpenAPI 3.1 spec (GET only — public). Served verbatim
	// from the embedded openapi.json sibling file.
	mux.HandleFunc("/openapi.json", HandleOpenAPI)

	// §8.1 credentials
	mux.HandleFunc("/api/v1/jackett/credentials", func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			d.Credentials.HandleListCredentials(w, r)
		case http.MethodPost:
			d.Credentials.HandleUpsertCredential(w, r)
		default:
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	})
	mux.HandleFunc("/api/v1/jackett/credentials/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodDelete {
			d.Credentials.HandleDeleteCredential(w, r)
			return
		}
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	})

	// §8.2 indexers
	mux.HandleFunc("/api/v1/jackett/indexers", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet {
			d.Indexers.HandleListIndexers(w, r)
			return
		}
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	})
	mux.HandleFunc("/api/v1/jackett/indexers/", func(w http.ResponseWriter, r *http.Request) {
		// Distinguish /indexers/{id}/test from /indexers/{id} by suffix.
		if strings.HasSuffix(r.URL.Path, "/test") && r.Method == http.MethodPost {
			d.Indexers.HandleTestIndexer(w, r)
			return
		}
		switch r.Method {
		case http.MethodPost:
			d.Indexers.HandleConfigureIndexer(w, r)
		case http.MethodDelete:
			d.Indexers.HandleDeleteIndexer(w, r)
		case http.MethodPatch:
			d.Indexers.HandlePatchIndexer(w, r)
		default:
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	})

	// §8.3 catalog
	mux.HandleFunc("/api/v1/jackett/catalog", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet {
			d.Catalog.HandleListCatalog(w, r)
			return
		}
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	})
	mux.HandleFunc("/api/v1/jackett/catalog/refresh", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			d.Catalog.HandleRefreshCatalog(w, r)
			return
		}
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	})

	// §8.4 autoconfig runs.
	//
	// The three /autoconfig/run* paths must be registered as listed below:
	//   - /autoconfig/runs        (exact, GET list)
	//   - /autoconfig/runs/       (prefix, GET by id — trailing slash is
	//                              required so stdlib ServeMux uses it as
	//                              a sub-tree match instead of exact)
	//   - /autoconfig/run         (exact, POST trigger)
	// stdlib ServeMux dispatches by longest-match exact path before any
	// trailing-slash subtree, so the three patterns are unambiguous.
	mux.HandleFunc("/api/v1/jackett/autoconfig/runs", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet {
			d.Runs.HandleListRuns(w, r)
			return
		}
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	})
	mux.HandleFunc("/api/v1/jackett/autoconfig/runs/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet {
			d.Runs.HandleGetRun(w, r)
			return
		}
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	})
	mux.HandleFunc("/api/v1/jackett/autoconfig/run", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			d.Runs.HandleTriggerRun(w, r)
			return
		}
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	})

	// §8.5 overrides
	mux.HandleFunc("/api/v1/jackett/overrides", func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			d.Overrides.HandleListOverrides(w, r)
		case http.MethodPost:
			d.Overrides.HandleUpsertOverride(w, r)
		default:
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	})
	mux.HandleFunc("/api/v1/jackett/overrides/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodDelete {
			d.Overrides.HandleDeleteOverride(w, r)
			return
		}
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	})

	// CORS wraps OUTSIDE auth so OPTIONS preflights short-circuit before
	// auth ever runs. Allowed origins default to the dashboard dev/prod
	// hosts; pass a custom list at NewMux time if you front it differently.
	return WithCORS(nil, WithAuth(mux))
}
