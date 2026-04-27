package jackettapi

import (
	"bytes"
	"crypto/rand"
	"database/sql"
	"encoding/json"
	"io"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/milos85vasic/qBitTorrent-go/internal/db"
	"github.com/milos85vasic/qBitTorrent-go/internal/db/repos"
)

// credsHarness wires a fresh DB + .env file + CredentialsDeps for each test.
// autoconfigCalls is a side-channel counter — production wraps this in
// `go jackett.Autoconfigure(...)`; the test stub just bumps the counter so
// tests can assert "the replay was triggered" without coupling to the real
// orchestrator (which would need a live Jackett to talk to).
type credsHarness struct {
	deps            *CredentialsDeps
	envPath         string
	conn            *sql.DB
	autoconfigCalls int
}

func newCredsHarness(t *testing.T) *credsHarness {
	t.Helper()
	dir := t.TempDir()
	conn, err := db.Open(filepath.Join(dir, "t.db"))
	if err != nil {
		t.Fatalf("db.Open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		t.Fatalf("rand: %v", err)
	}
	envPath := filepath.Join(dir, ".env")
	if err := os.WriteFile(envPath, []byte("FOO=bar\n"), 0o600); err != nil {
		t.Fatalf("seed env: %v", err)
	}
	h := &credsHarness{envPath: envPath, conn: conn}
	h.deps = &CredentialsDeps{
		Repo:              repos.NewCredentials(conn, key),
		Indexers:          repos.NewIndexers(conn),
		Jackett:           nil, // tests don't exercise the Jackett-side cascade
		EnvPath:           envPath,
		AutoconfigTrigger: func() { h.autoconfigCalls++ },
	}
	t.Cleanup(func() { _ = conn.Close() })
	return h
}

// strPtr is a helper for tests that need pointer-to-string literals.
func strPtr(s string) *string { return &s }

func TestListCredentialsNeverReturnsPlaintext(t *testing.T) {
	h := newCredsHarness(t)
	if err := h.deps.Repo.Upsert("RUTRACKER", "userpass", strPtr("plaintextU"), strPtr("plaintextP"), nil); err != nil {
		t.Fatalf("seed: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/credentials", nil)
	h.deps.HandleListCredentials(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	body := rec.Body.String()
	if strings.Contains(body, "plaintextU") || strings.Contains(body, "plaintextP") {
		t.Fatalf("PLAINTEXT LEAK: %s", body)
	}
	if !strings.Contains(body, `"has_username":true`) || !strings.Contains(body, `"has_password":true`) {
		t.Fatalf("has_* fields missing: %s", body)
	}
	if !strings.Contains(body, `"has_cookies":false`) {
		t.Fatalf("has_cookies should be false: %s", body)
	}
	// Sanity: response decodes to a JSON array of objects with the expected shape.
	var dtos []map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &dtos); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(dtos) != 1 {
		t.Fatalf("want 1 credential, got %d", len(dtos))
	}
	if dtos[0]["name"] != "RUTRACKER" {
		t.Fatalf("name: %v", dtos[0]["name"])
	}
	for _, banned := range []string{"username", "password", "cookies"} {
		if _, ok := dtos[0][banned]; ok {
			t.Fatalf("DTO must not include %q field; body=%s", banned, body)
		}
	}
}

func TestListCredentialsEmpty(t *testing.T) {
	h := newCredsHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/v1/jackett/credentials", nil)
	h.deps.HandleListCredentials(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d", rec.Code)
	}
	if strings.TrimSpace(rec.Body.String()) != "[]" {
		t.Fatalf("empty list should serialize as []; got %q", rec.Body.String())
	}
}

func TestPostCredentialAddsRowAndMirrorsToEnv(t *testing.T) {
	h := newCredsHarness(t)
	body := `{"name":"RUTRACKER","username":"u","password":"p"}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/credentials", strings.NewReader(body))
	h.deps.HandleUpsertCredential(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	got, err := h.deps.Repo.Get("RUTRACKER")
	if err != nil || got.Username != "u" || got.Password != "p" {
		t.Fatalf("db state: %+v err=%v", got, err)
	}
	if got.Kind != "userpass" {
		t.Fatalf("kind: want userpass, got %q", got.Kind)
	}
	envBytes, _ := os.ReadFile(h.envPath)
	envStr := string(envBytes)
	if !strings.Contains(envStr, "RUTRACKER_USERNAME=u") {
		t.Fatalf(".env missing username: %s", envStr)
	}
	if !strings.Contains(envStr, "RUTRACKER_PASSWORD=p") {
		t.Fatalf(".env missing password: %s", envStr)
	}
	if !strings.Contains(envStr, "FOO=bar") {
		t.Fatalf("unrelated key removed: %s", envStr)
	}
	if h.autoconfigCalls != 1 {
		t.Fatalf("autoconfig should be triggered once, got %d", h.autoconfigCalls)
	}
	// Response is a single DTO with no plaintext.
	respStr := rec.Body.String()
	if strings.Contains(respStr, `"u"`) || strings.Contains(respStr, `"p"`) {
		t.Fatalf("response leaked plaintext: %s", respStr)
	}
}

func TestPostCredentialCookieKind(t *testing.T) {
	h := newCredsHarness(t)
	body := `{"name":"NNMCLUB","cookies":"raw-cookie-blob"}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/credentials", strings.NewReader(body))
	h.deps.HandleUpsertCredential(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	got, err := h.deps.Repo.Get("NNMCLUB")
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if got.Kind != "cookie" {
		t.Fatalf("kind: want cookie, got %q", got.Kind)
	}
	if got.Cookies != "raw-cookie-blob" {
		t.Fatalf("cookies: %q", got.Cookies)
	}
	envBytes, _ := os.ReadFile(h.envPath)
	if !strings.Contains(string(envBytes), "NNMCLUB_COOKIES=raw-cookie-blob") {
		t.Fatalf(".env missing cookies: %s", envBytes)
	}
}

func TestPostCredentialPatchSemantics(t *testing.T) {
	h := newCredsHarness(t)
	if err := h.deps.Repo.Upsert("RUTRACKER", "userpass", strPtr("u1"), strPtr("p1"), nil); err != nil {
		t.Fatalf("seed: %v", err)
	}
	body := `{"name":"RUTRACKER","password":"p2"}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/credentials", strings.NewReader(body))
	h.deps.HandleUpsertCredential(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	got, _ := h.deps.Repo.Get("RUTRACKER")
	if got.Username != "u1" {
		t.Fatalf("username should be unchanged: got %q want u1", got.Username)
	}
	if got.Password != "p2" {
		t.Fatalf("password not updated: got %q want p2", got.Password)
	}
	// Existing kind preserved on partial update.
	if got.Kind != "userpass" {
		t.Fatalf("kind should be preserved: got %q want userpass", got.Kind)
	}
}

func TestPostCredentialPatchCookiesOnExistingUserpass(t *testing.T) {
	// Edge case from the plan: existing "userpass" row gets a PATCH with only
	// `cookies` — kind must NOT flip to "cookie"; spec PATCH semantics say
	// "only fields present are updated", which we extend to mean kind sticks
	// when the row already exists.
	h := newCredsHarness(t)
	if err := h.deps.Repo.Upsert("RUTRACKER", "userpass", strPtr("u1"), strPtr("p1"), nil); err != nil {
		t.Fatalf("seed: %v", err)
	}
	body := `{"name":"RUTRACKER","cookies":"sess=abc"}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/credentials", strings.NewReader(body))
	h.deps.HandleUpsertCredential(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status: %d body=%s", rec.Code, rec.Body.String())
	}
	got, _ := h.deps.Repo.Get("RUTRACKER")
	if got.Kind != "userpass" {
		t.Fatalf("existing kind should be preserved: got %q", got.Kind)
	}
	if got.Cookies != "sess=abc" {
		t.Fatalf("cookies not stored: %q", got.Cookies)
	}
}

func TestPostCredentialNoFields400(t *testing.T) {
	h := newCredsHarness(t)
	body := `{"name":"X"}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/credentials", strings.NewReader(body))
	h.deps.HandleUpsertCredential(rec, req)
	if rec.Code != 400 {
		t.Fatalf("expected 400, got %d body=%s", rec.Code, rec.Body.String())
	}
}

func TestPostCredentialMissingName400(t *testing.T) {
	h := newCredsHarness(t)
	body := `{"username":"u","password":"p"}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/credentials", strings.NewReader(body))
	h.deps.HandleUpsertCredential(rec, req)
	if rec.Code != 400 {
		t.Fatalf("expected 400, got %d", rec.Code)
	}
}

func TestPostCredentialJSONError400(t *testing.T) {
	h := newCredsHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/credentials", bytes.NewReader([]byte("not json")))
	h.deps.HandleUpsertCredential(rec, req)
	if rec.Code != 400 {
		t.Fatalf("expected 400 for bad JSON, got %d", rec.Code)
	}
}

func TestPostCredentialEnvWriteFailureRollsBackDB(t *testing.T) {
	h := newCredsHarness(t)
	// Force .env write failure: target a path whose parent directory does not
	// exist. envfile.Upsert opens `<path>.tmp` for writing, which will fail
	// because the parent dir is missing.
	h.deps.EnvPath = filepath.Join(t.TempDir(), "no-such-subdir", ".env")
	body := `{"name":"NEWCRED","username":"u","password":"p"}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/credentials", strings.NewReader(body))
	h.deps.HandleUpsertCredential(rec, req)
	if rec.Code != 500 {
		t.Fatalf("expected 500, got %d body=%s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), "env_write_failed_db_rolled_back") {
		t.Fatalf("error code missing: %s", rec.Body.String())
	}
	// Compensating rollback: row should NOT be in DB.
	if _, err := h.deps.Repo.Get("NEWCRED"); err == nil {
		t.Fatal("compensating rollback failed: row still in DB")
	}
	if h.autoconfigCalls != 0 {
		t.Fatalf("autoconfig must NOT be triggered on failure, got %d", h.autoconfigCalls)
	}
}

func TestPostCredentialEnvFailureRestoresPriorRow(t *testing.T) {
	// When .env mirror fails on an UPDATE (row pre-existed), the
	// compensating action must restore the prior values, not delete the row.
	h := newCredsHarness(t)
	if err := h.deps.Repo.Upsert("RUTRACKER", "userpass", strPtr("oldU"), strPtr("oldP"), nil); err != nil {
		t.Fatalf("seed: %v", err)
	}
	h.deps.EnvPath = filepath.Join(t.TempDir(), "no-such-subdir", ".env")
	body := `{"name":"RUTRACKER","password":"newP"}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/credentials", strings.NewReader(body))
	h.deps.HandleUpsertCredential(rec, req)
	if rec.Code != 500 {
		t.Fatalf("expected 500, got %d body=%s", rec.Code, rec.Body.String())
	}
	got, err := h.deps.Repo.Get("RUTRACKER")
	if err != nil {
		t.Fatalf("row was deleted by rollback (should have been restored): %v", err)
	}
	if got.Username != "oldU" || got.Password != "oldP" {
		t.Fatalf("rollback didn't restore prior values: %+v", got)
	}
}

func TestDeleteCredentialRemovesFromDBAndEnv(t *testing.T) {
	h := newCredsHarness(t)
	if err := h.deps.Repo.Upsert("RUTRACKER", "userpass", strPtr("u"), strPtr("p"), nil); err != nil {
		t.Fatalf("seed: %v", err)
	}
	if err := os.WriteFile(h.envPath, []byte("RUTRACKER_USERNAME=u\nRUTRACKER_PASSWORD=p\nFOO=bar\n"), 0o600); err != nil {
		t.Fatalf("seed env: %v", err)
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("DELETE", "/api/v1/jackett/credentials/RUTRACKER", nil)
	h.deps.HandleDeleteCredential(rec, req)
	if rec.Code != 204 {
		t.Fatalf("expected 204, got %d body=%s", rec.Code, rec.Body.String())
	}
	if _, err := h.deps.Repo.Get("RUTRACKER"); err == nil {
		t.Fatal("row still in DB")
	}
	body, _ := os.ReadFile(h.envPath)
	s := string(body)
	if strings.Contains(s, "RUTRACKER_USERNAME") || strings.Contains(s, "RUTRACKER_PASSWORD") {
		t.Fatalf(".env not cleaned: %s", s)
	}
	if !strings.Contains(s, "FOO=bar") {
		t.Fatalf("unrelated FOO removed: %s", s)
	}
}

func TestDeleteCredentialBadPathReturns400(t *testing.T) {
	h := newCredsHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("DELETE", "/api/v1/jackett/credentials/", nil)
	h.deps.HandleDeleteCredential(rec, req)
	if rec.Code != 400 {
		t.Fatalf("expected 400 for empty name, got %d", rec.Code)
	}
}

func TestDeleteCredentialIdempotent(t *testing.T) {
	// Spec §8.1 says DELETE returns 204; the underlying repo Delete is
	// idempotent (no error if row didn't exist). Confirm the handler is
	// likewise idempotent — deleting an absent name returns 204.
	h := newCredsHarness(t)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("DELETE", "/api/v1/jackett/credentials/MISSING", nil)
	h.deps.HandleDeleteCredential(rec, req)
	if rec.Code != 204 {
		t.Fatalf("expected 204 for missing name, got %d", rec.Code)
	}
}

// io.ReadAll guard against accidental imports
var _ = io.ReadAll
