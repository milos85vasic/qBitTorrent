package db

import (
	"database/sql"
	"embed"
	"fmt"
	"sort"
	"strconv"
	"strings"
)

//go:embed migrations/*.sql
var migrationsFS embed.FS

func Migrate(conn *sql.DB) error {
	if _, err := conn.Exec(`CREATE TABLE IF NOT EXISTS schema_migrations (
		version INTEGER PRIMARY KEY,
		applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
	)`); err != nil {
		return fmt.Errorf("create schema_migrations: %w", err)
	}
	applied := map[int]bool{}
	rows, err := conn.Query("SELECT version FROM schema_migrations")
	if err != nil {
		return fmt.Errorf("query versions: %w", err)
	}
	for rows.Next() {
		var v int
		_ = rows.Scan(&v)
		applied[v] = true
	}
	rows.Close()

	entries, err := migrationsFS.ReadDir("migrations")
	if err != nil {
		return fmt.Errorf("read migrations dir: %w", err)
	}
	type mig struct {
		version int
		name    string
	}
	var migs []mig
	for _, e := range entries {
		name := e.Name()
		if !strings.HasSuffix(name, ".sql") {
			continue
		}
		verStr := strings.SplitN(name, "_", 2)[0]
		v, err := strconv.Atoi(verStr)
		if err != nil {
			return fmt.Errorf("bad migration name %s: %w", name, err)
		}
		migs = append(migs, mig{v, name})
	}
	sort.Slice(migs, func(i, j int) bool { return migs[i].version < migs[j].version })

	for _, m := range migs {
		if applied[m.version] {
			continue
		}
		body, err := migrationsFS.ReadFile("migrations/" + m.name)
		if err != nil {
			return fmt.Errorf("read %s: %w", m.name, err)
		}
		tx, err := conn.Begin()
		if err != nil {
			return fmt.Errorf("begin tx for %s: %w", m.name, err)
		}
		if _, err := tx.Exec(string(body)); err != nil {
			tx.Rollback()
			return fmt.Errorf("apply %s: %w", m.name, err)
		}
		// 001_init.sql does its own schema_migrations INSERT.
		// Subsequent migrations rely on this stepper to track.
		if m.version > 1 {
			if _, err := tx.Exec("INSERT INTO schema_migrations(version) VALUES(?)", m.version); err != nil {
				tx.Rollback()
				return fmt.Errorf("record version %d: %w", m.version, err)
			}
		}
		if err := tx.Commit(); err != nil {
			return fmt.Errorf("commit %s: %w", m.name, err)
		}
	}
	return nil
}
