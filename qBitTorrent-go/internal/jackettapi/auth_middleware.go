// Package jackettapi houses the HTTP handlers and middleware for the
// boba-jackett service, which exposes Jackett credential, indexer, and
// catalog management endpoints on port 7189 (per spec §8 of
// docs/superpowers/plans/2026-04-27-jackett-management-ui-and-system-db.md).
//
// All mutating endpoints in this package are gated by [WithAuth], which
// enforces the project's hardcoded admin/admin HTTP Basic Auth credentials
// (see CLAUDE.md "Critical Constraints"). Read endpoints (GET/HEAD) pass
// through unauthenticated since they only return redacted metadata.
package jackettapi

import (
	"crypto/subtle"
	"encoding/base64"
	"net/http"
)

// adminUser/adminPass mirror the project's hardcoded WebUI credentials
// (CLAUDE.md "Critical Constraints"). Mutating requests must present
// these via HTTP Basic Auth.
const (
	adminUser = "admin"
	adminPass = "admin"
)

// expectedAuth is the pre-computed `Basic <base64>` header value.
// Computed at init to avoid recomputing on every request.
var expectedAuth = "Basic " + base64.StdEncoding.EncodeToString([]byte(adminUser+":"+adminPass))

// WithAuth wraps the inner handler so that any non-GET request must
// present the admin/admin HTTP Basic Auth header. GET / HEAD pass through.
//
// Why GET passes: read endpoints expose only redacted metadata (per spec
// §8.1 "Never returns plaintext values") and the dashboard polls them on
// page load before the user has typed admin/admin. Mutations (POST/PATCH/
// DELETE) do require auth — those are the operations that change DB / .env
// / Jackett state.
//
// Returns 401 with WWW-Authenticate hint on auth failure. Does NOT log
// the failed attempt (no rate limiting + no log = no oracle for credential
// guessing; the rate is bounded by the dashboard's own UI throttling).
//
// Header comparison uses [subtle.ConstantTimeCompare] to prevent timing
// attacks on the credential check.
func WithAuth(inner http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// OPTIONS is the CORS preflight method — by W3C spec it must
		// NOT carry credentials. Forwarding without auth lets the CORS
		// middleware (wrapped outside us) emit the proper preflight
		// response. If we required auth here, every browser-initiated
		// POST/PATCH/DELETE would fail at preflight before the actual
		// request ever reached the handler. (Caught by Playwright walk-
		// through Task 47 §11.10.)
		if r.Method == http.MethodGet || r.Method == http.MethodHead || r.Method == http.MethodOptions {
			inner.ServeHTTP(w, r)
			return
		}
		got := r.Header.Get("Authorization")
		if subtle.ConstantTimeCompare([]byte(got), []byte(expectedAuth)) != 1 {
			w.Header().Set("WWW-Authenticate", `Basic realm="boba-jackett"`)
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		inner.ServeHTTP(w, r)
	})
}
