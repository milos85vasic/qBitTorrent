package envfile

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
)

// writerMu guards concurrent Upsert/Delete invocations on any envfile.
// SQLite-style single-writer protection — simpler than per-path locks
// and the call rate is in writes-per-minute, not writes-per-second.
var writerMu sync.Mutex

// Upsert inserts or updates the given keys atomically (tmp + fsync +
// rename + parent-dir fsync). Existing comment lines and key order are
// preserved; new keys are appended in sorted order. Mode is forced to
// 0600 even if the file existed at a more permissive mode.
func Upsert(path string, kv map[string]string) error {
	writerMu.Lock()
	defer writerMu.Unlock()
	return mutate(path, func(lines []string) []string {
		seen := map[string]bool{}
		out := make([]string, 0, len(lines)+len(kv))
		for _, l := range lines {
			t := strings.TrimSpace(l)
			if t == "" || strings.HasPrefix(t, "#") {
				out = append(out, l)
				continue
			}
			eq := strings.IndexByte(t, '=')
			if eq < 0 {
				out = append(out, l)
				continue
			}
			k := strings.TrimSpace(t[:eq])
			if v, ok := kv[k]; ok {
				if seen[k] {
					continue // drop duplicates
				}
				out = append(out, fmt.Sprintf("%s=%s", k, v))
				seen[k] = true
				continue
			}
			out = append(out, l)
		}
		// append new keys (sorted for determinism)
		newKeys := make([]string, 0)
		for k := range kv {
			if !seen[k] {
				newKeys = append(newKeys, k)
			}
		}
		sort.Strings(newKeys)
		for _, k := range newKeys {
			out = append(out, fmt.Sprintf("%s=%s", k, kv[k]))
		}
		return out
	})
}

// Delete removes the given keys atomically. Comment lines and other
// keys are preserved. Mode is forced to 0600.
func Delete(path string, keys []string) error {
	writerMu.Lock()
	defer writerMu.Unlock()
	drop := map[string]bool{}
	for _, k := range keys {
		drop[k] = true
	}
	return mutate(path, func(lines []string) []string {
		out := make([]string, 0, len(lines))
		for _, l := range lines {
			t := strings.TrimSpace(l)
			if t == "" || strings.HasPrefix(t, "#") {
				out = append(out, l)
				continue
			}
			eq := strings.IndexByte(t, '=')
			if eq < 0 {
				out = append(out, l)
				continue
			}
			k := strings.TrimSpace(t[:eq])
			if drop[k] {
				continue
			}
			out = append(out, l)
		}
		return out
	})
}

// mutate is the atomic-write core: read → transform → write tmp →
// fsync → rename → fsync parent-dir. Caller is responsible for holding
// writerMu.
func mutate(path string, fn func([]string) []string) error {
	body, err := os.ReadFile(path)
	existedBefore := err == nil
	if err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("read: %w", err)
	}
	// Normalize CRLF to LF so Windows-edited .env files don't leave \r in values.
	text := strings.ReplaceAll(string(body), "\r\n", "\n")
	lines := []string{}
	if len(text) > 0 {
		lines = strings.Split(strings.TrimRight(text, "\n"), "\n")
	}
	out := fn(lines)
	// Don't materialize a placeholder file if input was missing AND nothing to write.
	if !existedBefore && len(out) == 0 {
		return nil
	}
	tmp := path + ".tmp"
	f, err := os.OpenFile(tmp, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0600)
	if err != nil {
		return fmt.Errorf("open tmp: %w", err)
	}
	if _, err := f.WriteString(strings.Join(out, "\n") + "\n"); err != nil {
		f.Close()
		os.Remove(tmp)
		return fmt.Errorf("write: %w", err)
	}
	if err := f.Sync(); err != nil {
		f.Close()
		os.Remove(tmp)
		return fmt.Errorf("fsync tmp: %w", err)
	}
	if err := f.Close(); err != nil {
		os.Remove(tmp)
		return fmt.Errorf("close tmp: %w", err)
	}
	if err := os.Chmod(tmp, 0600); err != nil {
		os.Remove(tmp)
		return fmt.Errorf("chmod tmp: %w", err)
	}
	if err := os.Rename(tmp, path); err != nil {
		os.Remove(tmp)
		return fmt.Errorf("rename: %w", err)
	}
	// fsync parent dir
	dir := filepath.Dir(path)
	d, err := os.Open(dir)
	if err == nil {
		_ = d.Sync()
		d.Close()
	}
	return nil
}
