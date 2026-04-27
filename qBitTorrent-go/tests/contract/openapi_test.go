//go:build contract

// Package contract — Layer 6 contract test for boba-jackett.
//
// Loads the published OpenAPI 3.1 spec at
// internal/jackettapi/openapi.json, boots the in-process service, and
// validates that EVERY response produced by EVERY (method, path) combo
// in the spec matches the spec-declared schema (status code AND body
// shape).
//
// CONST-XII: a missing `status` field, a wrong status code, or a 5xx
// surfaces here as a validation error against the response schema. The
// test would fail against any handler stub that doesn't match the
// declared contract.
//
// Run:
//
//	GOMAXPROCS=2 nice -n 19 ionice -c 3 go test -tags=contract \
//	  -race -count=1 ./tests/contract/ -v
package contract

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	"github.com/getkin/kin-openapi/openapi3"
	"github.com/getkin/kin-openapi/openapi3filter"
	legacyrouter "github.com/getkin/kin-openapi/routers/legacy"

	"github.com/milos85vasic/qBitTorrent-go/internal/bootstrap"
	"github.com/milos85vasic/qBitTorrent-go/internal/db"
	"github.com/milos85vasic/qBitTorrent-go/internal/db/repos"
	"github.com/milos85vasic/qBitTorrent-go/internal/jackett"
	"github.com/milos85vasic/qBitTorrent-go/internal/jackettapi"
)

// loadSpec reads the openapi.json from the source tree (via the test
// caller's runtime.Caller) and returns the parsed Doc.
func loadSpec(t *testing.T) *openapi3.T {
	t.Helper()
	_, thisFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatalf("runtime.Caller failed")
	}
	specPath := filepath.Join(filepath.Dir(thisFile),
		"..", "..", "internal", "jackettapi", "openapi.json")
	loader := &openapi3.Loader{Context: context.Background(), IsExternalRefsAllowed: false}
	doc, err := loader.LoadFromFile(specPath)
	if err != nil {
		t.Fatalf("load openapi.json: %v", err)
	}
	if err := doc.Validate(context.Background()); err != nil {
		t.Fatalf("openapi.json self-validate: %v", err)
	}
	return doc
}

// bootService boots a fresh in-process boba-jackett at a tmp DB / .env.
// Returns the test server + a teardown via t.Cleanup.
func bootService(t *testing.T) *httptest.Server {
	t.Helper()
	dir := t.TempDir()
	envPath := filepath.Join(dir, ".env")
	dbPath := filepath.Join(dir, "boba.db")
	if err := os.WriteFile(envPath, []byte(""), 0o600); err != nil {
		t.Fatalf("seed: %v", err)
	}
	key, _, err := bootstrap.EnsureMasterKey(envPath)
	if err != nil {
		t.Fatalf("EnsureMasterKey: %v", err)
	}
	conn, err := db.Open(dbPath)
	if err != nil {
		t.Fatalf("db.Open: %v", err)
	}
	t.Cleanup(func() { _ = conn.Close() })
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("Migrate: %v", err)
	}

	credsRepo := repos.NewCredentials(conn, key)
	indexersRepo := repos.NewIndexers(conn)
	catalogRepo := repos.NewCatalog(conn)
	runsRepo := repos.NewRuns(conn)
	overridesRepo := repos.NewOverrides(conn)
	jClient := jackett.NewClient("http://127.0.0.1:1", "") // unreachable on purpose

	deps := &jackettapi.Deps{
		Credentials: &jackettapi.CredentialsDeps{
			Repo: credsRepo, Indexers: indexersRepo, Jackett: jClient,
			EnvPath: envPath, AutoconfigTrigger: func() {},
		},
		Indexers: &jackettapi.IndexersDeps{
			Indexers: indexersRepo, Creds: credsRepo,
			Catalog: catalogRepo, Jackett: jClient,
		},
		Catalog: &jackettapi.CatalogDeps{Catalog: catalogRepo, Jackett: jClient},
		Runs: &jackettapi.RunsDeps{
			Repo: runsRepo,
			AutoconfigOnce: func() jackett.AutoconfigResult {
				// Mirror the runtime contract: every slice/map field
				// non-nil so JSON serializes [] / {} not null.
				return jackett.AutoconfigResult{
					RanAt:                 time.Now().UTC(),
					DiscoveredCredentials: []string{},
					MatchedIndexers:       map[string]string{},
					ConfiguredNow:         []string{},
					AlreadyPresent:        []string{},
					SkippedNoMatch:        []string{},
					SkippedAmbiguous:      []jackett.AmbiguousMatch{},
					ServedByNativePlugin:  []string{},
					Errors:                []string{},
				}
			},
		},
		Overrides: &jackettapi.OverridesDeps{Repo: overridesRepo},
		Health: &jackettapi.HealthDeps{
			DB: conn, Jackett: jClient, Version: "contract-test",
			StartTime: time.Now().UTC(),
		},
	}
	srv := httptest.NewServer(jackettapi.NewMux(deps))
	t.Cleanup(srv.Close)
	return srv
}

// reqSpec is one (method, path, body) combo to drive at the service.
// Body may be nil for GET/DELETE.
type reqSpec struct {
	method string
	path   string
	body   any
}

// representativeRequests returns one driver per (method, path) combo
// declared in the OpenAPI doc. Bodies are minimal but spec-conformant.
func representativeRequests() []reqSpec {
	return []reqSpec{
		{method: "GET", path: "/healthz"},
		{method: "GET", path: "/openapi.json"},
		{method: "GET", path: "/api/v1/jackett/credentials"},
		{method: "POST", path: "/api/v1/jackett/credentials",
			body: map[string]any{"name": "RUTRACKER", "username": "u", "password": "p"}},
		{method: "DELETE", path: "/api/v1/jackett/credentials/RUTRACKER"},
		{method: "GET", path: "/api/v1/jackett/indexers"},
		// POST /indexers/{id} requires a configured Jackett — the
		// in-process service points at an unreachable URL, so this
		// returns 502. The OpenAPI spec lists 502 as a valid
		// response code for this endpoint.
		{method: "POST", path: "/api/v1/jackett/indexers/rutracker",
			body: map[string]any{"credential_name": "RUTRACKER"}},
		{method: "PATCH", path: "/api/v1/jackett/indexers/rutracker",
			body: map[string]any{"enabled_for_search": false}},
		{method: "DELETE", path: "/api/v1/jackett/indexers/rutracker"},
		{method: "POST", path: "/api/v1/jackett/indexers/rutracker/test"},
		{method: "GET", path: "/api/v1/jackett/catalog"},
		// catalog/refresh against unreachable Jackett returns 502.
		{method: "POST", path: "/api/v1/jackett/catalog/refresh"},
		{method: "GET", path: "/api/v1/jackett/autoconfig/runs"},
		// /runs/{id} returns 404 since no rows exist; spec lists 404.
		{method: "GET", path: "/api/v1/jackett/autoconfig/runs/1"},
		{method: "POST", path: "/api/v1/jackett/autoconfig/run"},
		{method: "GET", path: "/api/v1/jackett/overrides"},
		{method: "POST", path: "/api/v1/jackett/overrides",
			body: map[string]any{"env_name": "RUTRACKER", "indexer_id": "rutracker_v2"}},
		{method: "DELETE", path: "/api/v1/jackett/overrides/RUTRACKER"},
	}
}

// TestOpenAPIContract drives every spec'd path with a representative
// request and validates the response against the schema.
//
// Falsification: change credentialDTO to drop `kind` field — the
// validator catches "required field missing" on POST /credentials.
func TestOpenAPIContract(t *testing.T) {
	doc := loadSpec(t)
	// Patch the spec's "servers" to point at our test server's URL so
	// the legacy router can resolve relative paths to the correct host.
	srv := bootService(t)
	doc.Servers = openapi3.Servers{{URL: srv.URL}}

	router, err := legacyrouter.NewRouter(doc)
	if err != nil {
		t.Fatalf("legacyrouter.NewRouter: %v", err)
	}

	requests := representativeRequests()
	var validationErrors []string
	for _, rs := range requests {
		var bodyR io.Reader
		if rs.body != nil {
			b, err := json.Marshal(rs.body)
			if err != nil {
				t.Fatalf("marshal %s %s: %v", rs.method, rs.path, err)
			}
			bodyR = bytes.NewReader(b)
		}

		req, err := http.NewRequest(rs.method, srv.URL+rs.path, bodyR)
		if err != nil {
			t.Fatalf("NewRequest %s %s: %v", rs.method, rs.path, err)
		}
		if rs.body != nil {
			req.Header.Set("Content-Type", "application/json")
		}
		// Mutating endpoints require admin/admin Basic auth.
		if rs.method != http.MethodGet && rs.method != http.MethodHead {
			req.SetBasicAuth("admin", "admin")
		}

		// Resolve route in the spec to know which Operation to validate
		// against.
		route, pathParams, err := router.FindRoute(req)
		if err != nil {
			validationErrors = append(validationErrors,
				fmt.Sprintf("FindRoute %s %s: %v", rs.method, rs.path, err))
			continue
		}

		// Validate the request against the spec.
		reqInput := &openapi3filter.RequestValidationInput{
			Request:    req,
			PathParams: pathParams,
			Route:      route,
			Options: &openapi3filter.Options{
				AuthenticationFunc: openapi3filter.NoopAuthenticationFunc,
			},
		}
		if err := openapi3filter.ValidateRequest(context.Background(), reqInput); err != nil {
			validationErrors = append(validationErrors,
				fmt.Sprintf("REQUEST INVALID %s %s: %v", rs.method, rs.path, err))
			continue
		}

		// Fire the request.
		resp, err := srv.Client().Do(req)
		if err != nil {
			t.Fatalf("Do %s %s: %v", rs.method, rs.path, err)
		}
		respBody, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		// Validate the response. Restore the body for the validator.
		respInput := &openapi3filter.ResponseValidationInput{
			RequestValidationInput: reqInput,
			Status:                 resp.StatusCode,
			Header:                 resp.Header,
			Body:                   io.NopCloser(bytes.NewReader(respBody)),
			Options: &openapi3filter.Options{
				AuthenticationFunc: openapi3filter.NoopAuthenticationFunc,
			},
		}
		if err := openapi3filter.ValidateResponse(context.Background(), respInput); err != nil {
			validationErrors = append(validationErrors, fmt.Sprintf(
				"RESPONSE INVALID %s %s status=%d body=%s: %v",
				rs.method, rs.path, resp.StatusCode,
				truncate(string(respBody), 400), err))
			continue
		}

		t.Logf("OK   %-6s %-50s status=%d", rs.method, rs.path, resp.StatusCode)
	}

	if len(validationErrors) > 0 {
		t.Fatalf("contract validation FAILED with %d errors:\n%s",
			len(validationErrors), strings.Join(validationErrors, "\n"))
	}
}

// truncate returns s clipped to maxLen with an ellipsis suffix when
// truncated. Used for compact error logs.
func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "…"
}
