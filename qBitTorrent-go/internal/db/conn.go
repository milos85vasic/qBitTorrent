package db

import (
	"database/sql"
	"fmt"
	"net/url"
	"os"
	"strings"

	_ "modernc.org/sqlite"
)

// dsnPathEscape percent-encodes characters in the database path that would
// confuse the modernc.org/sqlite DSN parser. The parser splits on the FIRST
// '?' to separate path from query (sqlite.go:newConn), so any literal '?'
// or '#' in the path silently truncates the query string and degrades
// pragmas (e.g. journal_mode falls back from WAL to delete).
//
// Spaces are encoded as %20 (NOT '+', which is form-encoding only).
// '/' is preserved so absolute paths still resolve correctly.
func dsnPathEscape(path string) string {
	// url.PathEscape encodes ?, #, %, and most other reserved chars while
	// leaving '/' alone — exactly what we want for a sqlite file path.
	// We then escape '%' literals that PathEscape leaves alone if any
	// snuck in pre-encoded, but PathEscape already double-encodes them, so
	// we're fine. Whitespace becomes %20 via PathEscape too.
	escaped := url.PathEscape(path)
	// PathEscape doesn't escape '+' — and modernc's DSN parser is fine
	// with raw '+'. No further work needed.
	return escaped
}

func Open(path string) (*sql.DB, error) {
	// modernc.org/sqlite uses _pragma=name(value) DSN syntax.
	// The DSN parser splits on the FIRST '?' (sqlite.go:newConn), so a
	// path containing '?', '#', or other reserved chars truncates the
	// query string and silently degrades journal_mode away from WAL.
	// Percent-encode the path component to defend against this.
	var dsn strings.Builder
	dsn.WriteString("file:")
	dsn.WriteString(dsnPathEscape(path))
	dsn.WriteString("?_pragma=journal_mode(WAL)&_pragma=foreign_keys(on)&_pragma=synchronous(NORMAL)")

	conn, err := sql.Open("sqlite", dsn.String()) // driver name "sqlite" (NOT "sqlite3") for modernc
	if err != nil {
		return nil, fmt.Errorf("sql.Open: %w", err)
	}
	conn.SetMaxOpenConns(1) // SQLite single-writer; reads also serialized for simplicity
	if err := conn.Ping(); err != nil {
		conn.Close()
		return nil, fmt.Errorf("ping: %w", err)
	}
	// Enforce 0600 on the SQLite database file. modernc.org/sqlite creates
	// the file with the process umask (typically 0644 on Linux), but boba.db
	// stores AES-GCM-encrypted credentials whose master key lives in
	// .env(0600) — the DB file must match. We chmod after the first
	// successful Ping() so the file definitely exists. WAL/SHM sidecars
	// are chmodded too on a best-effort basis; missing sidecars (no write
	// has happened yet) are fine.
	for _, p := range []string{path, path + "-wal", path + "-shm"} {
		if _, err := os.Stat(p); err == nil {
			if err := os.Chmod(p, 0o600); err != nil {
				conn.Close()
				return nil, fmt.Errorf("chmod %s 0600: %w", p, err)
			}
		}
	}
	return conn, nil
}
