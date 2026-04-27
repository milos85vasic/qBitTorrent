package bootstrap

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/milos85vasic/qBitTorrent-go/internal/envfile"
)

func TestEnsureMasterKeyGeneratesIfMissing(t *testing.T) {
	dir := t.TempDir()
	envP := filepath.Join(dir, ".env")
	os.WriteFile(envP, []byte("FOO=bar\n"), 0600)
	key, generated, err := EnsureMasterKey(envP)
	if err != nil {
		t.Fatalf("EnsureMasterKey: %v", err)
	}
	if !generated {
		t.Fatal("expected generated=true")
	}
	if len(key) != 32 {
		t.Fatalf("want 32 bytes, got %d", len(key))
	}
	body, _ := os.ReadFile(envP)
	if !strings.Contains(string(body), "BOBA_MASTER_KEY=") {
		t.Fatalf("key not persisted to .env:\n%s", body)
	}
	if !strings.Contains(string(body), "DO NOT LOSE") {
		t.Fatalf("warning header missing:\n%s", body)
	}
}

func TestEnsureMasterKeyIdempotent(t *testing.T) {
	dir := t.TempDir()
	envP := filepath.Join(dir, ".env")
	os.WriteFile(envP, []byte("BOBA_MASTER_KEY=00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff\n"), 0600)
	_, generated, _ := EnsureMasterKey(envP)
	if generated {
		t.Fatal("expected generated=false")
	}
}

func TestImportFromEnvBundlesTriples(t *testing.T) {
	src, _ := envfile.Parse(strings.NewReader(`RUTRACKER_USERNAME=u
RUTRACKER_PASSWORD=p
IPTORRENTS_COOKIES=c
INCOMPLETE_USERNAME=onlyuser
JACKETT_API_KEY=ignored
`))
	bundles := DiscoverCredentialBundles(src, defaultExclude())
	if len(bundles) != 2 {
		t.Fatalf("want 2 (RUTRACKER, IPTORRENTS), got %+v", bundles)
	}
	// Order MUST be deterministic (alphabetical by Name) so boot logs and
	// downstream import passes are reproducible across runs.
	if bundles[0].Name != "IPTORRENTS" {
		t.Fatalf("bundles[0].Name = %q, want IPTORRENTS", bundles[0].Name)
	}
	if bundles[1].Name != "RUTRACKER" {
		t.Fatalf("bundles[1].Name = %q, want RUTRACKER", bundles[1].Name)
	}
}

func TestEnsureMasterKeyDoesNotDuplicateHeader(t *testing.T) {
	dir := t.TempDir()
	envP := filepath.Join(dir, ".env")
	// Pre-seed: header present, key MISSING (the old crash-window state).
	seed := "FOO=bar\n\n# === BOBA SYSTEM ===\n# Master key for credential encryption-at-rest in config/boba.db.\n# DO NOT LOSE THIS — credentials become unrecoverable without it.\n# To rotate: see docs/BOBA_DATABASE.md § \"Key Rotation\".\n"
	if err := os.WriteFile(envP, []byte(seed), 0600); err != nil {
		t.Fatalf("seed: %v", err)
	}
	_, generated, err := EnsureMasterKey(envP)
	if err != nil {
		t.Fatalf("EnsureMasterKey: %v", err)
	}
	if !generated {
		t.Fatal("expected generated=true (key was missing)")
	}
	body, _ := os.ReadFile(envP)
	count := strings.Count(string(body), "=== BOBA SYSTEM ===")
	if count != 1 {
		t.Fatalf("header duplicated, count=%d:\n%s", count, body)
	}
}
