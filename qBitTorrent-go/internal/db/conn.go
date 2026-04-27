package db

import (
	"database/sql"
	"fmt"

	_ "modernc.org/sqlite"
)

func Open(path string) (*sql.DB, error) {
	// modernc.org/sqlite uses _pragma=name(value) DSN syntax.
	dsn := fmt.Sprintf("file:%s?_pragma=journal_mode(WAL)&_pragma=foreign_keys(on)&_pragma=synchronous(NORMAL)", path)
	conn, err := sql.Open("sqlite", dsn) // driver name "sqlite" (NOT "sqlite3") for modernc
	if err != nil {
		return nil, fmt.Errorf("sql.Open: %w", err)
	}
	conn.SetMaxOpenConns(1) // SQLite single-writer; reads also serialized for simplicity
	if err := conn.Ping(); err != nil {
		conn.Close()
		return nil, fmt.Errorf("ping: %w", err)
	}
	return conn, nil
}
