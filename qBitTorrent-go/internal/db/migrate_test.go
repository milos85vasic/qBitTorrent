package db

import (
	"path/filepath"
	"testing"
)

func TestMigrateAppliesSchema(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "test.db")
	conn, err := Open(path)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	defer conn.Close()
	if err := Migrate(conn); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	wantTables := []string{"credentials", "indexers", "catalog_cache", "autoconfig_runs", "indexer_map_overrides", "schema_migrations"}
	for _, tbl := range wantTables {
		var name string
		err := conn.QueryRow("SELECT name FROM sqlite_master WHERE type='table' AND name=?", tbl).Scan(&name)
		if err != nil {
			t.Errorf("table %s missing: %v", tbl, err)
		}
	}
}

func TestMigrateIdempotent(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "test.db")
	conn, _ := Open(path)
	defer conn.Close()
	if err := Migrate(conn); err != nil {
		t.Fatalf("first migrate: %v", err)
	}
	if err := Migrate(conn); err != nil {
		t.Fatalf("second migrate (should be no-op): %v", err)
	}
	var version int
	if err := conn.QueryRow("SELECT MAX(version) FROM schema_migrations").Scan(&version); err != nil {
		t.Fatalf("query version: %v", err)
	}
	if version != 1 {
		t.Fatalf("want version=1, got %d", version)
	}
}

func TestMigratePragmas(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "test.db")
	conn, _ := Open(path)
	defer conn.Close()
	_ = Migrate(conn)

	var jm string
	conn.QueryRow("PRAGMA journal_mode").Scan(&jm)
	if jm != "wal" {
		t.Errorf("journal_mode: want wal, got %s", jm)
	}
	var fk int
	conn.QueryRow("PRAGMA foreign_keys").Scan(&fk)
	if fk != 1 {
		t.Errorf("foreign_keys: want 1, got %d", fk)
	}
}

// TestOpenWithExoticPath regression-guards Issue 1: a path containing
// reserved URL characters (?, &, #) used to truncate the DSN query
// string and silently degrade journal_mode to "delete".
func TestOpenWithExoticPath(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "weird?name#1.db")
	conn, err := Open(path)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	defer conn.Close()
	var jm string
	if err := conn.QueryRow("PRAGMA journal_mode").Scan(&jm); err != nil {
		t.Fatalf("PRAGMA journal_mode: %v", err)
	}
	if jm != "wal" {
		t.Fatalf("journal_mode degraded to %q on exotic path", jm)
	}
}
