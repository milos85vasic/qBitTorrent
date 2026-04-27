//go:build integration

// Package integration — Layer 2 integration tests for boba-jackett against
// REAL SQLite + REAL .env files (no mocks). Jackett is NOT exercised here;
// the autoconfig replay path is covered by the Layer 3 e2e suite.
//
// CONST-XII (Anti-Bluff): every assertion below inspects user-observable
// state (DB rows, file content, file mode, parsed env). Any test here
// would FAIL against a no-op stub implementation. Falsification narrative
// per scenario is captured in trailing comments.
//
// Run:
//
//	GOMAXPROCS=2 nice -n 19 ionice -c 3 go test -tags=integration \
//	  -race -count=1 ./tests/integration/ -v
package integration

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http/httptest"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"testing"

	"github.com/milos85vasic/qBitTorrent-go/internal/bootstrap"
	"github.com/milos85vasic/qBitTorrent-go/internal/db"
	"github.com/milos85vasic/qBitTorrent-go/internal/db/repos"
	"github.com/milos85vasic/qBitTorrent-go/internal/envfile"
	"github.com/milos85vasic/qBitTorrent-go/internal/jackettapi"
)

// hexKeyRE matches a 64-char lower-case-or-mixed-case hex string. Used to
// validate the BOBA_MASTER_KEY value the bootstrap step writes.
var hexKeyRE = regexp.MustCompile(`^[0-9a-fA-F]{64}$`)

// freshTestEnv constructs a fresh DB + .env for a single test scenario.
// Returns the credentials repo, the env path, and a cleanup hook.
func freshTestEnv(t *testing.T, seedEnvBody string) (
	creds *repos.Credentials,
	indexers *repos.Indexers,
	envPath string,
	dbPath string,
	masterKey []byte,
) {
	t.Helper()
	dir := t.TempDir()
	envPath = filepath.Join(dir, ".env")
	dbPath = filepath.Join(dir, "boba.db")
	if err := os.WriteFile(envPath, []byte(seedEnvBody), 0o600); err != nil {
		t.Fatalf("seed env: %v", err)
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
		t.Fatalf("db.Migrate: %v", err)
	}
	creds = repos.NewCredentials(conn, key)
	indexers = repos.NewIndexers(conn)
	masterKey = key
	return
}

// TestBootstrap_EmptyEnvCreatesKey covers spec §10.2 scenario 1: empty
// .env → bootstrap generates a key, persists it, mode 0600, hex 64 chars.
//
// Falsification: replace [bootstrap.EnsureMasterKey] with a no-op that
// returns make([]byte, 32) without writing the file — the
// hexKeyRE-against-disk-contents assertion fails because no
// `BOBA_MASTER_KEY=` line is found.
func TestBootstrap_EmptyEnvCreatesKey(t *testing.T) {
	dir := t.TempDir()
	envPath := filepath.Join(dir, ".env")
	if err := os.WriteFile(envPath, []byte(""), 0o600); err != nil {
		t.Fatalf("seed: %v", err)
	}

	key, generated, err := bootstrap.EnsureMasterKey(envPath)
	if err != nil {
		t.Fatalf("EnsureMasterKey: %v", err)
	}
	if !generated {
		t.Fatalf("expected `generated=true` on empty .env")
	}
	if len(key) != 32 {
		t.Fatalf("key must be 32 bytes (AES-256), got %d", len(key))
	}

	// Inspect actual file content & mode.
	body, err := os.ReadFile(envPath)
	if err != nil {
		t.Fatalf("read after bootstrap: %v", err)
	}
	st, err := os.Stat(envPath)
	if err != nil {
		t.Fatalf("stat: %v", err)
	}
	if mode := st.Mode().Perm(); mode != 0o600 {
		t.Fatalf("file mode must be 0600 after bootstrap, got %o", mode)
	}

	parsed, err := envfile.Parse(bytes.NewReader(body))
	if err != nil {
		t.Fatalf("parse persisted env: %v", err)
	}
	gotHex, ok := parsed["BOBA_MASTER_KEY"]
	if !ok {
		t.Fatalf("BOBA_MASTER_KEY not persisted; file=%q", string(body))
	}
	if !hexKeyRE.MatchString(gotHex) {
		t.Fatalf("BOBA_MASTER_KEY does not match %s; got %q", hexKeyRE, gotHex)
	}
	// Round-trip: hex-decoded value MUST equal the in-memory key.
	decoded, err := hex.DecodeString(gotHex)
	if err != nil {
		t.Fatalf("hex decode persisted key: %v", err)
	}
	if !bytes.Equal(decoded, key) {
		t.Fatalf("on-disk key != in-memory key — bootstrap diverged")
	}

	// Header sentinel must be present so operators see the warning block.
	if !strings.Contains(string(body), "=== BOBA SYSTEM ===") {
		t.Fatalf("master-key header sentinel missing; body=%q", string(body))
	}
}

// TestBootstrap_ImportNTriples covers spec §10.2 scenario 2: env with N
// triples → DiscoverCredentialBundles + write to repo → List() returns N
// rows AND each Get(name) decrypts to original plaintext.
//
// Falsification: stub Credentials.Upsert to no-op — the Get assertion
// returns ErrNotFound (or wrong plaintext under a partial stub) and the
// test fails before reaching the count check.
func TestBootstrap_ImportNTriples(t *testing.T) {
	seed := strings.Join([]string{
		"# pre-existing comment",
		"FOO=bar",
		"RUTRACKER_USERNAME=ru-user-XYZ",
		"RUTRACKER_PASSWORD=ru-pass-PQR",
		"KINOZAL_USERNAME=kz-user-ABC",
		"KINOZAL_PASSWORD=kz-pass-DEF",
		"IPTORRENTS_COOKIES=cf_clearance=fake; uid=1234",
		"",
	}, "\n")
	creds, _, envPath, _, _ := freshTestEnv(t, seed)

	body, err := os.ReadFile(envPath)
	if err != nil {
		t.Fatalf("read env: %v", err)
	}
	parsed, err := envfile.Parse(bytes.NewReader(body))
	if err != nil {
		t.Fatalf("parse env: %v", err)
	}

	bundles := bootstrap.DiscoverCredentialBundles(parsed, map[string]bool{
		"BOBA": true, "QBITTORRENT": true, "JACKETT": true, "FOO": true,
	})
	if len(bundles) != 3 {
		names := make([]string, 0, len(bundles))
		for _, b := range bundles {
			names = append(names, b.Name)
		}
		t.Fatalf("want 3 bundles (RUTRACKER, KINOZAL, IPTORRENTS); got %d: %v",
			len(bundles), names)
	}

	// Write each bundle to the encrypted repo.
	for _, b := range bundles {
		kind := "userpass"
		if b.Cookies != "" && b.Username == "" && b.Password == "" {
			kind = "cookie"
		}
		var u, p, c *string
		if b.Username != "" {
			u = &b.Username
		}
		if b.Password != "" {
			p = &b.Password
		}
		if b.Cookies != "" {
			c = &b.Cookies
		}
		if err := creds.Upsert(b.Name, kind, u, p, c); err != nil {
			t.Fatalf("Upsert %s: %v", b.Name, err)
		}
	}

	rows, err := creds.List()
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(rows) != 3 {
		t.Fatalf("want 3 credentials in DB; got %d", len(rows))
	}

	expect := map[string]bootstrap.CredBundle{
		"RUTRACKER":  {Name: "RUTRACKER", Username: "ru-user-XYZ", Password: "ru-pass-PQR"},
		"KINOZAL":    {Name: "KINOZAL", Username: "kz-user-ABC", Password: "kz-pass-DEF"},
		"IPTORRENTS": {Name: "IPTORRENTS", Cookies: "cf_clearance=fake; uid=1234"},
	}
	for name, want := range expect {
		got, err := creds.Get(name)
		if err != nil {
			t.Fatalf("Get %s: %v", name, err)
		}
		if got.Username != want.Username {
			t.Fatalf("%s.Username decrypt mismatch: want=%q got=%q",
				name, want.Username, got.Username)
		}
		if got.Password != want.Password {
			t.Fatalf("%s.Password decrypt mismatch: want=%q got=%q",
				name, want.Password, got.Password)
		}
		if got.Cookies != want.Cookies {
			t.Fatalf("%s.Cookies decrypt mismatch: want=%q got=%q",
				name, want.Cookies, got.Cookies)
		}
	}
}

// TestBootstrap_RestartIdempotent covers spec §10.2 scenario 3: re-running
// bootstrap with the same .env produces no DB row count change AND no
// error.
//
// Falsification: replace EnsureMasterKey to always-generate — second call
// generates a NEW key, the existing rows still encrypt under the old key
// and decrypt fails on Get (the row count assertion would still pass, but
// the decrypt round-trip catches it).
func TestBootstrap_RestartIdempotent(t *testing.T) {
	seed := strings.Join([]string{
		"RUTRACKER_USERNAME=u1",
		"RUTRACKER_PASSWORD=p1",
		"",
	}, "\n")
	creds, _, envPath, _, key1 := freshTestEnv(t, seed)
	u, p := "u1", "p1"
	if err := creds.Upsert("RUTRACKER", "userpass", &u, &p, nil); err != nil {
		t.Fatalf("seed Upsert: %v", err)
	}
	rows1, _ := creds.List()
	if len(rows1) != 1 {
		t.Fatalf("seed row count: got %d want 1", len(rows1))
	}

	// Re-run EnsureMasterKey — must return the SAME key, generated=false,
	// and not corrupt the file.
	key2, generated, err := bootstrap.EnsureMasterKey(envPath)
	if err != nil {
		t.Fatalf("EnsureMasterKey re-run: %v", err)
	}
	if generated {
		t.Fatalf("re-run must NOT report `generated=true`")
	}
	if !bytes.Equal(key1, key2) {
		t.Fatalf("master key changed between runs: was=%x now=%x", key1, key2)
	}

	rows2, err := creds.List()
	if err != nil {
		t.Fatalf("post-restart List: %v", err)
	}
	if len(rows2) != len(rows1) {
		t.Fatalf("row count changed across restart: was=%d now=%d",
			len(rows1), len(rows2))
	}
	got, err := creds.Get("RUTRACKER")
	if err != nil {
		t.Fatalf("post-restart Get: %v", err)
	}
	if got.Username != "u1" || got.Password != "p1" {
		t.Fatalf("decrypt mismatch post-restart: %+v", got)
	}
}

// TestUI_AddCredViaHandler covers spec §10.2 scenario 4: POST via the
// real handler → DB row exists AND .env has both USERNAME + PASSWORD
// lines AND existing comments preserved.
//
// Falsification: stub envfile.Upsert to no-op — the .env content
// assertion (must contain RUTRACKER_USERNAME=) fails.
func TestUI_AddCredViaHandler(t *testing.T) {
	seed := "# OPERATOR COMMENT\nFOO=bar\n"
	creds, idx, envPath, _, _ := freshTestEnv(t, seed)

	autoconfigCalls := 0
	deps := &jackettapi.CredentialsDeps{
		Repo:              creds,
		Indexers:          idx,
		EnvPath:           envPath,
		AutoconfigTrigger: func() { autoconfigCalls++ },
	}

	body := `{"name":"RUTRACKER","username":"alpha","password":"bravo"}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/credentials",
		strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	deps.HandleUpsertCredential(rec, req)

	if rec.Code != 200 {
		t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
	}

	// DB row content: decrypted plaintext matches.
	got, err := creds.Get("RUTRACKER")
	if err != nil {
		t.Fatalf("Get after handler: %v", err)
	}
	if got.Username != "alpha" || got.Password != "bravo" {
		t.Fatalf("decrypt mismatch: %+v", got)
	}

	// .env content: both lines present, original comment preserved.
	envBytes, err := os.ReadFile(envPath)
	if err != nil {
		t.Fatalf("read env: %v", err)
	}
	envStr := string(envBytes)
	for _, want := range []string{
		"RUTRACKER_USERNAME=alpha",
		"RUTRACKER_PASSWORD=bravo",
		"# OPERATOR COMMENT", // existing comment must survive
		"FOO=bar",            // pre-existing key must survive
	} {
		if !strings.Contains(envStr, want) {
			t.Fatalf("env missing %q after handler; full=%q", want, envStr)
		}
	}

	// Plaintext password MUST NOT appear in the response body (DTO is
	// metadata-only).
	if strings.Contains(rec.Body.String(), "alpha") ||
		strings.Contains(rec.Body.String(), "bravo") {
		t.Fatalf("response body LEAKED plaintext: %s", rec.Body.String())
	}

	// Autoconfig trigger fired exactly once.
	if autoconfigCalls != 1 {
		t.Fatalf("autoconfig trigger calls: got %d want 1", autoconfigCalls)
	}
}

// TestUI_DeleteCredViaHandler covers spec §10.2 scenario 5: DELETE
// removes both DB row AND .env lines (specifically only the named lines;
// other rows preserved).
//
// Falsification: stub envfile.Delete to no-op — the .env-must-NOT-contain
// assertion catches the leak.
func TestUI_DeleteCredViaHandler(t *testing.T) {
	seed := strings.Join([]string{
		"# OPERATOR COMMENT",
		"FOO=bar",
		"RUTRACKER_USERNAME=alpha",
		"RUTRACKER_PASSWORD=bravo",
		"KINOZAL_USERNAME=keep-me",
		"KINOZAL_PASSWORD=keep-me-too",
		"",
	}, "\n")
	creds, idx, envPath, _, _ := freshTestEnv(t, seed)

	// Pre-populate both rows.
	a, b := "alpha", "bravo"
	c, d := "keep-me", "keep-me-too"
	if err := creds.Upsert("RUTRACKER", "userpass", &a, &b, nil); err != nil {
		t.Fatalf("seed RU: %v", err)
	}
	if err := creds.Upsert("KINOZAL", "userpass", &c, &d, nil); err != nil {
		t.Fatalf("seed KZ: %v", err)
	}

	deps := &jackettapi.CredentialsDeps{
		Repo:     creds,
		Indexers: idx,
		EnvPath:  envPath,
	}

	rec := httptest.NewRecorder()
	req := httptest.NewRequest("DELETE",
		"/api/v1/jackett/credentials/RUTRACKER", nil)
	deps.HandleDeleteCredential(rec, req)
	if rec.Code != 204 {
		t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
	}

	// DB: RUTRACKER gone, KINOZAL remains.
	if _, err := creds.Get("RUTRACKER"); err == nil {
		t.Fatalf("RUTRACKER must be gone from DB after DELETE")
	}
	if got, err := creds.Get("KINOZAL"); err != nil {
		t.Fatalf("KINOZAL must survive: %v", err)
	} else if got.Username != "keep-me" {
		t.Fatalf("KINOZAL plaintext lost: %+v", got)
	}

	// .env: RUTRACKER_* gone, others preserved.
	envBytes, err := os.ReadFile(envPath)
	if err != nil {
		t.Fatalf("read env: %v", err)
	}
	envStr := string(envBytes)
	for _, banned := range []string{
		"RUTRACKER_USERNAME",
		"RUTRACKER_PASSWORD",
	} {
		if strings.Contains(envStr, banned) {
			t.Fatalf("env still contains %q after DELETE: %s", banned, envStr)
		}
	}
	for _, want := range []string{
		"# OPERATOR COMMENT",
		"FOO=bar",
		"KINOZAL_USERNAME=keep-me",
		"KINOZAL_PASSWORD=keep-me-too",
	} {
		if !strings.Contains(envStr, want) {
			t.Fatalf("env LOST %q after DELETE; got: %s", want, envStr)
		}
	}
}

// TestConcurrentDashboardWrites covers spec §10.2 scenario 6: 50
// concurrent goroutines each upsert a unique credential. Post-state:
// .env parses cleanly, DB has 50 rows, every .env line maps to a DB row.
//
// Falsification: drop the writerMu in envfile.Upsert and run the race
// detector — atomic-rename interleaving leaves a half-written .env that
// envfile.Parse rejects (or fewer than 50 distinct keys survive).
func TestConcurrentDashboardWrites(t *testing.T) {
	const N = 50

	creds, idx, envPath, _, _ := freshTestEnv(t,
		"# preserved comment\nINITIAL=value\n")

	deps := &jackettapi.CredentialsDeps{
		Repo:     creds,
		Indexers: idx,
		EnvPath:  envPath,
		// AutoconfigTrigger intentionally nil — 50 goroutines firing into
		// a no-op closure would race on the counter without buying
		// observability we'd assert on; the dashboard's intent is
		// already covered by the single-write test above.
	}

	var (
		wg       sync.WaitGroup
		failures int64
	)
	wg.Add(N)
	for i := 0; i < N; i++ {
		go func(i int) {
			defer wg.Done()
			rand32 := make([]byte, 16)
			_, _ = rand.Read(rand32)
			body := fmt.Sprintf(`{"name":"TRACKER_%02d","username":"u%d","password":"p%s"}`,
				i, i, hex.EncodeToString(rand32))
			rec := httptest.NewRecorder()
			req := httptest.NewRequest("POST",
				"/api/v1/jackett/credentials", strings.NewReader(body))
			req.Header.Set("Content-Type", "application/json")
			deps.HandleUpsertCredential(rec, req)
			if rec.Code != 200 {
				atomic.AddInt64(&failures, 1)
				t.Logf("goroutine %d failed: code=%d body=%s",
					i, rec.Code, rec.Body.String())
			}
			runtime.Gosched()
		}(i)
	}
	wg.Wait()

	if atomic.LoadInt64(&failures) > 0 {
		t.Fatalf("%d goroutines failed under load", failures)
	}

	// (a) .env parses cleanly.
	envBytes, err := os.ReadFile(envPath)
	if err != nil {
		t.Fatalf("read env: %v", err)
	}
	parsed, err := envfile.Parse(bytes.NewReader(envBytes))
	if err != nil {
		t.Fatalf("env failed to parse after concurrent writes: %v\n--- BODY ---\n%s",
			err, envBytes)
	}
	// Pre-existing INITIAL must survive.
	if parsed["INITIAL"] != "value" {
		t.Fatalf("pre-existing key INITIAL was clobbered: parsed=%v", parsed)
	}

	// (b) DB has 50 rows.
	rows, err := creds.List()
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(rows) != N {
		names := make([]string, 0, len(rows))
		for _, r := range rows {
			names = append(names, r.Name)
		}
		sort.Strings(names)
		t.Fatalf("DB has %d rows, want %d. names=%v", len(rows), N, names)
	}

	// (c) every .env TRACKER_NN_USERNAME line maps to a DB row.
	envNames := map[string]bool{}
	for k := range parsed {
		if strings.HasPrefix(k, "TRACKER_") && strings.HasSuffix(k, "_USERNAME") {
			n := strings.TrimSuffix(k, "_USERNAME")
			envNames[n] = true
		}
	}
	if len(envNames) != N {
		t.Fatalf(".env has %d TRACKER_*_USERNAME keys, want %d",
			len(envNames), N)
	}
	dbNames := map[string]bool{}
	for _, r := range rows {
		dbNames[r.Name] = true
	}
	for n := range envNames {
		if !dbNames[n] {
			t.Fatalf(".env mentions %q but DB does not", n)
		}
	}
	for n := range dbNames {
		if !envNames[n] {
			t.Fatalf("DB has %q but .env does not (drift)", n)
		}
	}
}

// Compile-time anti-bluff: the JSON DTO must not include plaintext
// fields. We pin this by decoding a sample response and asserting the
// fields explicitly. Not part of the §10.2 list but cheap and adds a
// belt-and-braces guarantee against future regressions where someone
// adds a Username field to credentialDTO.
func TestPostResponseShapeNeverIncludesPlaintext(t *testing.T) {
	creds, idx, envPath, _, _ := freshTestEnv(t, "")
	deps := &jackettapi.CredentialsDeps{
		Repo: creds, Indexers: idx, EnvPath: envPath,
	}
	body := `{"name":"X","username":"sentinel-username","password":"sentinel-password"}`
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/v1/jackett/credentials",
		strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	deps.HandleUpsertCredential(rec, req)
	if rec.Code != 200 {
		t.Fatalf("code=%d body=%s", rec.Code, rec.Body.String())
	}
	if strings.Contains(rec.Body.String(), "sentinel-username") ||
		strings.Contains(rec.Body.String(), "sentinel-password") {
		t.Fatalf("LEAK: response body contains plaintext sentinel: %s",
			rec.Body.String())
	}
	var dto map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &dto); err != nil {
		t.Fatalf("decode: %v", err)
	}
	for _, banned := range []string{"username", "password", "cookies"} {
		if _, ok := dto[banned]; ok {
			t.Fatalf("DTO must not include %q: %v", banned, dto)
		}
	}
}
