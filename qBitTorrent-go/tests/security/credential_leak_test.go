//go:build security

// Package security — Layer 4 leak tests for boba-jackett.
//
// The single most-important assertion in the boba-jackett project: if a
// plaintext credential ever leaves the encrypted DB row, this test
// catches it.
//
// Strategy: insert 6 high-entropy random credentials via the real HTTP
// API, capture all log output, capture every GET response body, capture
// /proc/self/environ, capture the raw DB file, then grep all four
// channels for each plaintext value. Hits in (logs, response bodies,
// /proc/environ) MUST be 0; the DB hex MUST contain ZERO raw plaintext
// matches AND must decrypt with the right key.
//
// CONST-XII: every assertion is "the secret string is NOT in this byte
// buffer." A no-op redactor (Write returns p verbatim) would emit the
// password to the captured log buffer and the test would fail.
//
// Run:
//
//	GOMAXPROCS=2 nice -n 19 ionice -c 3 go test -tags=security \
//	  -race -count=1 ./tests/security/ -v
package security

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/bootstrap"
	"github.com/milos85vasic/qBitTorrent-go/internal/db"
	"github.com/milos85vasic/qBitTorrent-go/internal/db/repos"
	"github.com/milos85vasic/qBitTorrent-go/internal/jackett"
	"github.com/milos85vasic/qBitTorrent-go/internal/jackettapi"
	"github.com/milos85vasic/qBitTorrent-go/internal/logging"
)

// secretsHarness owns the in-process boba-jackett, the redactor-wrapped
// log buffer, and a list of plaintext secrets the test seeded.
type secretsHarness struct {
	srv     *httptest.Server
	logBuf  *syncBuffer
	envPath string
	dbPath  string
	repo    *repos.Credentials
	secrets map[string]secretBundle
	key     []byte
}

// secretBundle pairs a plaintext value with the credential name it
// belongs to.
type secretBundle struct {
	Username string
	Password string
}

// syncBuffer is a thread-safe bytes.Buffer wrapper. The redactor's Write
// is invoked under sync.RWMutex internally, but the buffer also fields
// concurrent reads via Bytes().
type syncBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (s *syncBuffer) Write(p []byte) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.buf.Write(p)
}

func (s *syncBuffer) Bytes() []byte {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]byte, s.buf.Len())
	copy(out, s.buf.Bytes())
	return out
}

func newSecretsHarness(t *testing.T) *secretsHarness {
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
	repo := repos.NewCredentials(conn, key)
	indexers := repos.NewIndexers(conn)
	catalog := repos.NewCatalog(conn)
	runs := repos.NewRuns(conn)
	overrides := repos.NewOverrides(conn)

	// Wrap the global log writer with the redactor — exactly the same
	// install main.go does at boot.
	logBuf := &syncBuffer{}
	redactor := logging.NewRedactor(logBuf)
	prevWriter := log.Writer()
	prevFlags := log.Flags()
	log.SetOutput(redactor)
	t.Cleanup(func() {
		log.SetOutput(prevWriter)
		log.SetFlags(prevFlags)
	})

	jClient := jackett.NewClient("http://127.0.0.1:1", "") // unreachable on purpose

	deps := &jackettapi.Deps{
		Credentials: &jackettapi.CredentialsDeps{
			Repo: repo, Indexers: indexers, Jackett: jClient,
			EnvPath: envPath,
			AutoconfigTrigger: func() {
				// Mirror main.go: register every plaintext on the
				// redactor before logging.
			},
		},
		Indexers: &jackettapi.IndexersDeps{
			Indexers: indexers, Creds: repo, Catalog: catalog, Jackett: jClient,
		},
		Catalog: &jackettapi.CatalogDeps{Catalog: catalog, Jackett: jClient},
		Runs: &jackettapi.RunsDeps{
			Repo:           runs,
			AutoconfigOnce: func() jackett.AutoconfigResult { return jackett.AutoconfigResult{} },
		},
		Overrides: &jackettapi.OverridesDeps{Repo: overrides},
		Health: &jackettapi.HealthDeps{
			DB: conn, Jackett: jClient, Version: "sec-test",
			StartTime: time.Now().UTC(),
		},
	}

	srv := httptest.NewServer(jackettapi.NewMux(deps))
	t.Cleanup(srv.Close)

	h := &secretsHarness{
		srv: srv, logBuf: logBuf, envPath: envPath, dbPath: dbPath,
		repo: repo, secrets: map[string]secretBundle{}, key: key,
	}
	// Insert 6 high-entropy creds.
	for i := 0; i < 6; i++ {
		bU := make([]byte, 16)
		bP := make([]byte, 16)
		_, _ = rand.Read(bU)
		_, _ = rand.Read(bP)
		// Add a recognizable prefix so on-failure logs identify which
		// secret leaked.
		uPlain := "secU-" + hex.EncodeToString(bU)
		pPlain := "secP-" + hex.EncodeToString(bP)
		name := "TRACKER_" + hex.EncodeToString([]byte{byte(i)})
		h.secrets[name] = secretBundle{Username: uPlain, Password: pPlain}
		// Register on the redactor BEFORE the upsert (mirror main.go's
		// "preload from List+Get at boot" + "AddSecret on rotate").
		redactor.AddSecret(uPlain)
		redactor.AddSecret(pPlain)
		// Insert via the API — exercise the entire write path.
		raw, _ := json.Marshal(map[string]any{
			"name": name, "username": uPlain, "password": pPlain,
		})
		req, _ := http.NewRequest("POST", srv.URL+"/api/v1/jackett/credentials",
			bytes.NewReader(raw))
		req.Header.Set("Content-Type", "application/json")
		req.SetBasicAuth("admin", "admin")
		resp, err := srv.Client().Do(req)
		if err != nil {
			t.Fatalf("seed %s: %v", name, err)
		}
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if resp.StatusCode != 200 {
			t.Fatalf("seed %s: %d body=%s", name, resp.StatusCode, body)
		}
	}
	// Force a few log lines to flow through the redactor.
	log.Printf("security harness: seeded %d credentials", len(h.secrets))
	for name, sec := range h.secrets {
		// Deliberate: log a string that DOES contain the plaintext,
		// to verify the redactor masks it. If the redactor were a
		// no-op, this line would put the secret in the log buffer.
		log.Printf("debug: rotated %s username=%s password=%s", name,
			sec.Username, sec.Password)
	}
	return h
}

// TestNoCredentialLeak is the central anti-bluff gate for credentials.
//
// Falsification: replace logging.Redactor.Write with `return r.dest.Write(p)`
// (no replacement) — the captured log buffer would contain every
// plaintext seeded in the harness setup, and the "logs hits" assertion
// would fail with detailed output.
func TestNoCredentialLeak(t *testing.T) {
	h := newSecretsHarness(t)

	// 1) Capture log output. The redactor was installed in setup; harness
	// already emitted log lines containing plaintext, all of which must
	// have been masked.
	logBytes := h.logBuf.Bytes()

	// 2) Capture every API GET response body.
	endpoints := []string{
		"/healthz",
		"/openapi.json",
		"/api/v1/jackett/credentials",
		"/api/v1/jackett/indexers",
		"/api/v1/jackett/catalog",
		"/api/v1/jackett/autoconfig/runs",
		"/api/v1/jackett/overrides",
	}
	var allBodies bytes.Buffer
	for _, p := range endpoints {
		resp, err := h.srv.Client().Get(h.srv.URL + p)
		if err != nil {
			t.Fatalf("GET %s: %v", p, err)
		}
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		allBodies.WriteString("=== " + p + " ===\n")
		allBodies.Write(body)
		allBodies.WriteByte('\n')
	}

	// 3) Capture /proc/self/environ. Treat as best-effort (Linux-only
	// path; on non-Linux dev hosts skip the channel check).
	procEnviron, _ := os.ReadFile("/proc/self/environ")

	// 4) Read the raw DB file; capture full hex dump.
	dbBytes, err := os.ReadFile(h.dbPath)
	if err != nil {
		t.Fatalf("read db: %v", err)
	}
	dbHex := hex.EncodeToString(dbBytes)

	// 5) For each plaintext, assert all four channels:
	for name, sec := range h.secrets {
		for _, plaintext := range []string{sec.Username, sec.Password} {
			// (a) logs — MUST be 0 hits.
			if bytes.Contains(logBytes, []byte(plaintext)) {
				t.Fatalf("LEAK in logs for %s: %q\n--- LOG ---\n%s",
					name, plaintext, logBytes)
			}
			// (b) response bodies — MUST be 0 hits.
			if bytes.Contains(allBodies.Bytes(), []byte(plaintext)) {
				t.Fatalf("LEAK in API responses for %s: %q\n--- BODIES ---\n%s",
					name, plaintext, allBodies.String())
			}
			// (c) /proc/self/environ — MUST be 0 hits.
			if len(procEnviron) > 0 &&
				bytes.Contains(procEnviron, []byte(plaintext)) {
				t.Fatalf("LEAK in /proc/self/environ for %s: %q",
					name, plaintext)
			}
			// (d) DB hex — MUST be 0 raw matches (encrypted, not plaintext).
			plainHex := hex.EncodeToString([]byte(plaintext))
			if strings.Contains(dbHex, plainHex) {
				t.Fatalf("LEAK in DB raw for %s: plaintext bytes appear unencrypted",
					name)
			}
		}
	}

	// 6) Round-trip: with the right key, decrypt MUST recover plaintext.
	for name, want := range h.secrets {
		got, err := h.repo.Get(name)
		if err != nil {
			t.Fatalf("Get %s: %v", name, err)
		}
		if got.Username != want.Username || got.Password != want.Password {
			t.Fatalf("decrypt mismatch %s: want=%+v got=%+v", name, want, got)
		}
	}

	// 7) With the WRONG key, decrypt MUST fail. Re-open the same DB
	// file with a fresh random key and try to read a row; the underlying
	// AES-GCM Open must surface an error.
	bogusKey := make([]byte, 32)
	_, _ = rand.Read(bogusKey)
	conn2, err := db.Open(h.dbPath)
	if err != nil {
		t.Fatalf("re-open db: %v", err)
	}
	defer conn2.Close()
	bogusRepo := repos.NewCredentials(conn2, bogusKey)
	for name := range h.secrets {
		if _, err := bogusRepo.Get(name); err == nil {
			t.Fatalf("decrypt with WRONG key SUCCEEDED for %s — encryption broken!",
				name)
		}
	}
}

// TestEnvFilePermissions asserts the on-disk .env file has 0600 mode.
//
// Falsification: change Atomic to write 0644 — this test catches it.
func TestEnvFilePermissions(t *testing.T) {
	h := newSecretsHarness(t)
	st, err := os.Stat(h.envPath)
	if err != nil {
		t.Fatalf("stat: %v", err)
	}
	if mode := st.Mode().Perm(); mode != 0o600 {
		t.Fatalf(".env mode=%o, want 0600", mode)
	}
}
