// Package bootstrap handles first-run system initialization: master key
// autogeneration (persisted back to .env) and discovery of legacy
// credential triples (NAME_USERNAME / NAME_PASSWORD / NAME_COOKIES) for
// migration into the encrypted credentials table.
//
// This package only produces in-memory results — wiring discovered
// bundles into the credentials repo happens in main during boot.
package bootstrap

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"os"
	"strings"

	"github.com/milos85vasic/qBitTorrent-go/internal/envfile"
)

const masterKeyHeader = `# === BOBA SYSTEM ===
# Master key for credential encryption-at-rest in config/boba.db.
# DO NOT LOSE THIS — credentials become unrecoverable without it.
# To rotate: see docs/BOBA_DATABASE.md § "Key Rotation".`

// masterKeyHeaderSentinel is the ASCII-only stable prefix used to detect
// "is the header already in this file" without depending on the Unicode
// em-dash literal in masterKeyHeader.
const masterKeyHeaderSentinel = "=== BOBA SYSTEM ==="

// EnsureMasterKey reads envPath, returns the existing BOBA_MASTER_KEY if
// one is present and well-formed (64 hex chars / 32 bytes), or generates
// a fresh 32-byte AES-256 key, persists it back to envPath under a
// commented header, and returns it. The bool return indicates whether a
// new key was generated.
func EnsureMasterKey(envPath string) (key []byte, generated bool, err error) {
	f, err := os.Open(envPath)
	if err != nil {
		return nil, false, fmt.Errorf("open .env: %w", err)
	}
	parsed, err := envfile.Parse(f)
	f.Close()
	if err != nil {
		return nil, false, fmt.Errorf("parse .env: %w", err)
	}
	if existing, ok := parsed["BOBA_MASTER_KEY"]; ok && len(existing) == 64 {
		if k, err := hex.DecodeString(existing); err == nil && len(k) == 32 {
			return k, false, nil
		}
	}
	raw := make([]byte, 32)
	if _, err := rand.Read(raw); err != nil {
		return nil, false, fmt.Errorf("rand.Read: %w", err)
	}
	hexKey := hex.EncodeToString(raw)
	// Single atomic write: strip any pre-existing BOBA_MASTER_KEY, append
	// the warning header (only if not already present), and append the
	// new key — all in one tmp+fsync+rename+dir-fsync pass. This closes
	// the crash window where a generated key could be lost between two
	// separate writes (silent data-loss for credentials encrypted in the
	// crashed boot, since next boot would regenerate a different key).
	if err := envfile.Atomic(envPath, func(lines []string) []string {
		// 1) Strip any existing BOBA_MASTER_KEY line(s) — we re-add at end.
		kept := make([]string, 0, len(lines)+8)
		for _, l := range lines {
			t := strings.TrimSpace(l)
			if strings.HasPrefix(t, "BOBA_MASTER_KEY=") {
				continue
			}
			kept = append(kept, l)
		}
		// 2) Append header block ONLY if not already present.
		joined := strings.Join(kept, "\n")
		if !strings.Contains(joined, masterKeyHeaderSentinel) {
			// separator blank line if file is non-empty and last line is non-blank
			if len(kept) > 0 && strings.TrimSpace(kept[len(kept)-1]) != "" {
				kept = append(kept, "")
			}
			kept = append(kept, strings.Split(masterKeyHeader, "\n")...)
		}
		// 3) Append the key.
		kept = append(kept, "BOBA_MASTER_KEY="+hexKey)
		return kept
	}); err != nil {
		return nil, false, fmt.Errorf("atomic write: %w", err)
	}
	// Re-read and verify the key on disk equals the in-memory `raw` we
	// are about to return — defends against silent on-disk divergence.
	v, err := os.Open(envPath)
	if err != nil {
		return nil, false, fmt.Errorf("verify open: %w", err)
	}
	got, err := envfile.Parse(v)
	v.Close()
	if err != nil {
		return nil, false, fmt.Errorf("verify parse: %w", err)
	}
	if got["BOBA_MASTER_KEY"] != hexKey {
		return nil, false, fmt.Errorf("verify mismatch: persisted key does not equal generated key")
	}
	return raw, true, nil
}

var defaultExcludeSet = map[string]bool{
	"QBITTORRENT": true, "JACKETT": true, "WEBUI": true,
	"PROXY": true, "MERGE": true, "BRIDGE": true, "BOBA": true,
}

// defaultExclude returns a fresh copy of the default name-prefix denylist
// used when scanning .env for credential triples. A copy is returned so
// callers may mutate without affecting the package default.
func defaultExclude() map[string]bool {
	out := make(map[string]bool, len(defaultExcludeSet))
	for k, v := range defaultExcludeSet {
		out[k] = v
	}
	return out
}
