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

	"github.com/milos85vasic/qBitTorrent-go/internal/envfile"
)

const masterKeyHeader = `# === BOBA SYSTEM ===
# Master key for credential encryption-at-rest in config/boba.db.
# DO NOT LOSE THIS — credentials become unrecoverable without it.
# To rotate: see docs/BOBA_DATABASE.md § "Key Rotation".`

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
		k, err := hex.DecodeString(existing)
		if err == nil && len(k) == 32 {
			return k, false, nil
		}
	}
	raw := make([]byte, 32)
	if _, err := rand.Read(raw); err != nil {
		return nil, false, fmt.Errorf("rand.Read: %w", err)
	}
	hexKey := hex.EncodeToString(raw)
	// Append header (as comments) then key
	body, err := os.ReadFile(envPath)
	if err != nil {
		return nil, false, fmt.Errorf("read .env: %w", err)
	}
	out := string(body)
	if len(out) > 0 && out[len(out)-1] != '\n' {
		out += "\n"
	}
	out += "\n" + masterKeyHeader + "\n"
	if err := os.WriteFile(envPath+".tmp", []byte(out), 0600); err != nil {
		return nil, false, fmt.Errorf("write tmp: %w", err)
	}
	if err := os.Rename(envPath+".tmp", envPath); err != nil {
		return nil, false, fmt.Errorf("rename: %w", err)
	}
	if err := envfile.Upsert(envPath, map[string]string{"BOBA_MASTER_KEY": hexKey}); err != nil {
		return nil, false, fmt.Errorf("upsert key: %w", err)
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
