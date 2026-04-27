// Package jackettapi — OpenAPI 3.1 spec endpoint (Task 22, spec §8).
//
// The spec itself lives in the sibling openapi.json file and is embedded
// into the binary via the //go:embed directive. Editing openapi.json
// (the source of truth) is a code change — rebuild + redeploy to roll
// it out. The shape of every documented schema is pinned by tests in
// openapi_test.go (TestOpenAPISpecCoversAllSpecPaths,
// TestCredentialDTOSchemaHasNoPlaintextFields).
//
// Why hand-written instead of generated: the surface is small (14 path
// entries), the handlers are stable, and pulling in a generator
// (e.g. swaggo, kin-openapi) would add a transitive dependency for
// little benefit. The spec doubles as documentation; keeping it close
// to the handlers makes drift visible at PR review time.
package jackettapi

import (
	_ "embed"
	"net/http"
)

// openapiJSON is the OpenAPI 3.1 spec, embedded at build time from the
// sibling openapi.json file. The byte slice is read-only.
//
//go:embed openapi.json
var openapiJSON []byte

// HandleOpenAPI handles GET /openapi.json. Serves the embedded OpenAPI
// 3.1 spec verbatim with Content-Type: application/json. The spec is
// the authoritative description of every spec §8 endpoint and is what
// the dashboard's API client should target.
func HandleOpenAPI(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(openapiJSON)
}
