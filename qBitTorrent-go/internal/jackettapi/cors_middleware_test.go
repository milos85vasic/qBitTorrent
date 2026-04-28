package jackettapi

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// markerPostHandler is a stand-in inner handler that records that it was
// reached. CORS+OPTIONS must NOT reach it; the OPTIONS short-circuit
// is the critical CONST-XII assertion.
func markerPostHandler(reached *bool) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		*reached = true
		w.WriteHeader(http.StatusOK)
	})
}

func TestWithCORS_AllowedOriginGetsACAOHeader(t *testing.T) {
	var reached bool
	h := WithCORS(nil, markerPostHandler(&reached))
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/x", nil)
	req.Header.Set("Origin", "http://localhost:4200")
	h.ServeHTTP(rec, req)
	if got := rec.Header().Get("Access-Control-Allow-Origin"); got != "http://localhost:4200" {
		t.Fatalf("want ACAO=http://localhost:4200, got %q", got)
	}
	if got := rec.Header().Get("Vary"); !strings.Contains(got, "Origin") {
		t.Fatalf("want Vary contains Origin, got %q", got)
	}
	if !reached {
		t.Fatal("inner handler NOT reached on GET — CORS should not block")
	}
}

func TestWithCORS_DisallowedOriginGetsNoCORSHeaders(t *testing.T) {
	var reached bool
	h := WithCORS(nil, markerPostHandler(&reached))
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/x", nil)
	req.Header.Set("Origin", "http://evil.example")
	h.ServeHTTP(rec, req)
	if got := rec.Header().Get("Access-Control-Allow-Origin"); got != "" {
		t.Fatalf("disallowed origin should NOT echo ACAO; got %q", got)
	}
	// Inner handler IS reached (we don't block at the server) — the
	// browser will block based on missing ACAO. This matches the W3C
	// spec; CORS is browser-side enforcement.
	if !reached {
		t.Fatal("inner handler should still be reached even for disallowed origin")
	}
}

func TestWithCORS_OPTIONSPreflightShortCircuits(t *testing.T) {
	var reached bool
	h := WithCORS(nil, markerPostHandler(&reached))
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodOptions, "/api/v1/jackett/credentials", nil)
	req.Header.Set("Origin", "http://localhost:4200")
	req.Header.Set("Access-Control-Request-Method", "POST")
	req.Header.Set("Access-Control-Request-Headers", "Authorization, Content-Type")
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusNoContent {
		t.Fatalf("OPTIONS preflight: want 204, got %d", rec.Code)
	}
	if reached {
		t.Fatal("inner handler MUST NOT be reached for OPTIONS preflight (CONST-XII)")
	}
	allowMethods := rec.Header().Get("Access-Control-Allow-Methods")
	for _, m := range []string{"GET", "POST", "PATCH", "DELETE", "OPTIONS"} {
		if !strings.Contains(allowMethods, m) {
			t.Errorf("Allow-Methods missing %s: %q", m, allowMethods)
		}
	}
	allowHeaders := rec.Header().Get("Access-Control-Allow-Headers")
	for _, h := range []string{"Authorization", "Content-Type"} {
		if !strings.Contains(allowHeaders, h) {
			t.Errorf("Allow-Headers missing %s: %q", h, allowHeaders)
		}
	}
}

func TestWithCORS_CustomOriginsList(t *testing.T) {
	var reached bool
	h := WithCORS([]string{"https://prod.example"}, markerPostHandler(&reached))
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/x", nil)
	req.Header.Set("Origin", "https://prod.example")
	h.ServeHTTP(rec, req)
	if rec.Header().Get("Access-Control-Allow-Origin") != "https://prod.example" {
		t.Fatalf("custom origin should be allowed; got %q", rec.Header().Get("Access-Control-Allow-Origin"))
	}
	// Default origins NOT applied when a custom list is passed:
	rec2 := httptest.NewRecorder()
	req2 := httptest.NewRequest("GET", "/x", nil)
	req2.Header.Set("Origin", "http://localhost:4200")
	h.ServeHTTP(rec2, req2)
	if rec2.Header().Get("Access-Control-Allow-Origin") != "" {
		t.Fatalf("default localhost:4200 should NOT be allowed when custom list given; got %q",
			rec2.Header().Get("Access-Control-Allow-Origin"))
	}
}

func TestWithCORS_WildcardAllowsAnyOrigin(t *testing.T) {
	var reached bool
	h := WithCORS([]string{"*"}, markerPostHandler(&reached))
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/x", nil)
	req.Header.Set("Origin", "http://192.168.1.42:7187")
	h.ServeHTTP(rec, req)
	if got := rec.Header().Get("Access-Control-Allow-Origin"); got != "http://192.168.1.42:7187" {
		t.Fatalf("wildcard: want ACAO echoed back, got %q", got)
	}
	if !reached {
		t.Fatal("inner handler NOT reached")
	}
}

func TestWithCORS_EnvVarOverridesDefaults(t *testing.T) {
	t.Setenv("ALLOWED_ORIGINS", "http://phone.local:7187")
	var reached bool
	h := WithCORS(nil, markerPostHandler(&reached))
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/x", nil)
	req.Header.Set("Origin", "http://phone.local:7187")
	h.ServeHTTP(rec, req)
	if got := rec.Header().Get("Access-Control-Allow-Origin"); got != "http://phone.local:7187" {
		t.Fatalf("env var origin: want ACAO=http://phone.local:7187, got %q", got)
	}
	// Default origin should no longer be allowed
	rec2 := httptest.NewRecorder()
	req2 := httptest.NewRequest("GET", "/x", nil)
	req2.Header.Set("Origin", "http://localhost:7187")
	h.ServeHTTP(rec2, req2)
	if rec2.Header().Get("Access-Control-Allow-Origin") != "" {
		t.Fatalf("default origin should NOT be allowed when env var overrides; got %q",
			rec2.Header().Get("Access-Control-Allow-Origin"))
	}
}

func TestAuthMiddleware_OPTIONSPassesWithoutAuth(t *testing.T) {
	// Anti-bluff regression for the auth middleware fix: OPTIONS
	// (browser CORS preflight) must pass through without auth.
	var reached bool
	h := WithAuth(markerPostHandler(&reached))
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodOptions, "/api/v1/jackett/credentials", nil)
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("OPTIONS without auth: want 200 (passed through to inner), got %d", rec.Code)
	}
	if !reached {
		t.Fatal("inner handler NOT reached for OPTIONS — auth middleware should pass it through")
	}
}
