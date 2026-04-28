package jackettapi

import (
	"net/http"
	"strings"
)

// defaultAllowedOrigins are the dashboard origins permitted by CORS by
// default. Add more via WithCORSOrigins if needed in production.
var defaultAllowedOrigins = []string{
	"http://localhost:4200",   // ng serve dev server
	"http://127.0.0.1:4200", // ng serve dev server (IPv4)
	"http://localhost:7187",   // merge service Angular SPA
	"http://127.0.0.1:7187",   // merge service Angular SPA (IPv4)
}

// WithCORS wraps an inner handler with permissive-but-allowlisted CORS:
//   - the request's Origin header must match one of allowedOrigins
//     (exact prefix match; no wildcards) — otherwise no CORS headers are
//     emitted and the browser blocks the response per same-origin policy.
//   - all standard methods (GET/HEAD/POST/PATCH/PUT/DELETE/OPTIONS) are
//     allowed.
//   - Authorization + Content-Type are the allowed request headers
//     (matches what the dashboard actually sends).
//   - OPTIONS preflight short-circuits with 204 + CORS headers BEFORE
//     reaching the inner handler. The inner handler (auth middleware)
//     also passes OPTIONS through, but the short-circuit avoids the
//     extra round-trip when the preflight has nothing to do.
//
// CONST-XII: this middleware is regression-guarded by the Playwright
// walkthroughs in frontend/e2e/ — if CORS breaks, every dialog-driven
// POST/PATCH/DELETE in the dashboard fails at the browser layer, and
// the Playwright assertion on the post-action DOM state catches it.
func WithCORS(allowedOrigins []string, inner http.Handler) http.Handler {
	if len(allowedOrigins) == 0 {
		allowedOrigins = defaultAllowedOrigins
	}
	allow := make(map[string]bool, len(allowedOrigins))
	for _, o := range allowedOrigins {
		allow[strings.ToLower(strings.TrimRight(o, "/"))] = true
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if origin != "" && allow[strings.ToLower(strings.TrimRight(origin, "/"))] {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Vary", "Origin")
			w.Header().Set("Access-Control-Allow-Methods",
				"GET, HEAD, POST, PATCH, PUT, DELETE, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers",
				"Authorization, Content-Type")
			w.Header().Set("Access-Control-Max-Age", "600") // cache preflight 10 min
		}
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		inner.ServeHTTP(w, r)
	})
}
