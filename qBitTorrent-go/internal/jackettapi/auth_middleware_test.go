package jackettapi

import (
	"encoding/base64"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// markerHandler responds 200 OK with a sentinel body so we can detect that
// the auth middleware actually invoked the inner handler.
var markerHandler = http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("inner-reached"))
})

func TestWithAuthGETPassesWithoutHeader(t *testing.T) {
	h := WithAuth(markerHandler)
	req := httptest.NewRequest(http.MethodGet, "/api/v1/jackett/credentials", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("GET without auth: want 200, got %d", rec.Code)
	}
	body, _ := io.ReadAll(rec.Body)
	if string(body) != "inner-reached" {
		t.Fatalf("inner not invoked, body=%q", body)
	}
}

func TestWithAuthHEADPassesWithoutHeader(t *testing.T) {
	h := WithAuth(markerHandler)
	req := httptest.NewRequest(http.MethodHead, "/api/v1/jackett/credentials", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("HEAD without auth: want 200, got %d", rec.Code)
	}
}

func TestWithAuthPOSTRejectedWithoutHeader(t *testing.T) {
	h := WithAuth(markerHandler)
	req := httptest.NewRequest(http.MethodPost, "/api/v1/jackett/credentials", strings.NewReader("{}"))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("POST without auth: want 401, got %d", rec.Code)
	}
	if got := rec.Header().Get("WWW-Authenticate"); !strings.Contains(got, "Basic") {
		t.Fatalf("WWW-Authenticate header missing/wrong: %q", got)
	}
}

func TestWithAuthPATCHRejectedWithoutHeader(t *testing.T) {
	h := WithAuth(markerHandler)
	req := httptest.NewRequest(http.MethodPatch, "/api/v1/jackett/indexers/x", strings.NewReader("{}"))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("PATCH without auth: want 401, got %d", rec.Code)
	}
}

func TestWithAuthDELETERejectedWithoutHeader(t *testing.T) {
	h := WithAuth(markerHandler)
	req := httptest.NewRequest(http.MethodDelete, "/api/v1/jackett/credentials/x", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("DELETE without auth: want 401, got %d", rec.Code)
	}
}

func TestWithAuthPOSTAcceptedWithCorrectHeader(t *testing.T) {
	h := WithAuth(markerHandler)
	req := httptest.NewRequest(http.MethodPost, "/api/v1/jackett/credentials", strings.NewReader("{}"))
	auth := "Basic " + base64.StdEncoding.EncodeToString([]byte("admin:admin"))
	req.Header.Set("Authorization", auth)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("POST with admin/admin: want 200, got %d body=%q", rec.Code, rec.Body.String())
	}
}

func TestWithAuthPOSTRejectedWithWrongPassword(t *testing.T) {
	h := WithAuth(markerHandler)
	req := httptest.NewRequest(http.MethodPost, "/api/v1/jackett/credentials", strings.NewReader("{}"))
	auth := "Basic " + base64.StdEncoding.EncodeToString([]byte("admin:wrongpass"))
	req.Header.Set("Authorization", auth)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("POST with wrong password: want 401, got %d", rec.Code)
	}
}
