package jackettapi

import (
	"encoding/json"
	"net/http/httptest"
	"sort"
	"strings"
	"testing"
	"time"
)

// TestHandleOpenAPIServesEmbeddedSpec is the smoke that the embedded
// JSON byte slice is non-empty, the handler writes 200, and the
// content-type is application/json. A regression here would mean either
// the //go:embed directive failed or someone replaced the spec with a
// stub.
func TestHandleOpenAPIServesEmbeddedSpec(t *testing.T) {
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/openapi.json", nil)
	HandleOpenAPI(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d", rec.Code)
	}
	if got := rec.Header().Get("Content-Type"); got != "application/json" {
		t.Fatalf("content-type: %s", got)
	}
	if rec.Body.Len() < 100 {
		t.Fatalf("body too short: %d bytes", rec.Body.Len())
	}
}

// TestOpenAPISpecIsValidJSON parses the embedded byte slice as JSON and
// asserts the OpenAPI 3.1 envelope shape. CONST-XII: this check verifies
// real structure, not just "looks like JSON".
func TestOpenAPISpecIsValidJSON(t *testing.T) {
	var doc map[string]any
	if err := json.Unmarshal(openapiJSON, &doc); err != nil {
		t.Fatalf("openapi.json is not valid JSON: %v", err)
	}
	if doc["openapi"] != "3.1.0" {
		t.Fatalf("openapi version: %v", doc["openapi"])
	}
	info, ok := doc["info"].(map[string]any)
	if !ok {
		t.Fatalf("info missing")
	}
	if title, _ := info["title"].(string); title == "" {
		t.Fatalf("info.title empty")
	}
	if version, _ := info["version"].(string); version == "" {
		t.Fatalf("info.version empty")
	}
}

// TestOpenAPISpecCoversAllSpecPaths is the anti-bluff guard for spec
// coverage. Every spec §8 path (plus /healthz, /openapi.json) MUST be
// present. A future PR that adds an endpoint without documenting it
// here will fail this test.
func TestOpenAPISpecCoversAllSpecPaths(t *testing.T) {
	var doc map[string]any
	if err := json.Unmarshal(openapiJSON, &doc); err != nil {
		t.Fatalf("parse: %v", err)
	}
	paths, ok := doc["paths"].(map[string]any)
	if !ok {
		t.Fatalf("paths missing")
	}
	if len(paths) < 14 {
		t.Fatalf("expected >=14 paths, got %d: %v", len(paths), keysOf(paths))
	}
	required := []string{
		"/healthz",
		"/openapi.json",
		"/api/v1/jackett/credentials",
		"/api/v1/jackett/credentials/{name}",
		"/api/v1/jackett/indexers",
		"/api/v1/jackett/indexers/{id}",
		"/api/v1/jackett/indexers/{id}/test",
		"/api/v1/jackett/catalog",
		"/api/v1/jackett/catalog/refresh",
		"/api/v1/jackett/autoconfig/runs",
		"/api/v1/jackett/autoconfig/runs/{id}",
		"/api/v1/jackett/autoconfig/run",
		"/api/v1/jackett/overrides",
		"/api/v1/jackett/overrides/{env_name}",
	}
	for _, p := range required {
		if _, ok := paths[p]; !ok {
			t.Errorf("missing path: %s", p)
		}
	}
}

// TestCredentialDTOSchemaHasNoPlaintextFields is the anti-bluff guard
// for the spec §8.1 "Never returns plaintext values" contract. The
// CredentialDTO response schema must NOT enumerate username / password
// / cookies as properties — only has_* booleans and metadata. The
// CredentialPostBody (request) is intentionally exempt: the operator
// is submitting plaintext when creating credentials.
func TestCredentialDTOSchemaHasNoPlaintextFields(t *testing.T) {
	var doc map[string]any
	if err := json.Unmarshal(openapiJSON, &doc); err != nil {
		t.Fatalf("parse: %v", err)
	}
	components, ok := doc["components"].(map[string]any)
	if !ok {
		t.Fatal("components missing")
	}
	schemas, ok := components["schemas"].(map[string]any)
	if !ok {
		t.Fatal("schemas missing")
	}
	cred, ok := schemas["CredentialDTO"].(map[string]any)
	if !ok {
		t.Fatal("CredentialDTO schema missing")
	}
	props, ok := cred["properties"].(map[string]any)
	if !ok {
		t.Fatal("CredentialDTO.properties missing")
	}
	for _, forbidden := range []string{"username", "password", "cookies"} {
		if _, present := props[forbidden]; present {
			t.Errorf("CredentialDTO must not expose plaintext field: %q", forbidden)
		}
	}
	for _, required := range []string{"has_username", "has_password", "has_cookies"} {
		if _, present := props[required]; !present {
			t.Errorf("CredentialDTO missing required field: %q", required)
		}
	}
}

// TestRouterWiresOpenAPIEndpoint verifies the mux dispatches GET
// /openapi.json to HandleOpenAPI. This is the integration check that
// router.go calls mux.HandleFunc("/openapi.json", HandleOpenAPI).
func TestRouterWiresOpenAPIEndpoint(t *testing.T) {
	deps := &Deps{
		Health: &HealthDeps{Version: "test", StartTime: time.Now()},
	}
	mux := NewMux(deps)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/openapi.json", nil)
	mux.ServeHTTP(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"openapi"`) {
		t.Fatalf("body missing openapi key: %s", rec.Body.String()[:min(200, rec.Body.Len())])
	}
}

func keysOf(m map[string]any) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}
