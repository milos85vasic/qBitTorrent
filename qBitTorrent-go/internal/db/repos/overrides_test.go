package repos

import (
	"path/filepath"
	"testing"

	"github.com/milos85vasic/qBitTorrent-go/internal/db"
)

func overridesConn(t *testing.T) *Overrides {
	t.Helper()
	dir := t.TempDir()
	conn, err := db.Open(filepath.Join(dir, "t.db"))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	return NewOverrides(conn)
}

func TestOverridesUpsertList(t *testing.T) {
	r := overridesConn(t)
	if err := r.Upsert("NNMCLUB", "nnmclub-alt"); err != nil {
		t.Fatalf("Upsert: %v", err)
	}
	rows, err := r.List()
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(rows) != 1 || rows[0].EnvName != "NNMCLUB" || rows[0].IndexerID != "nnmclub-alt" {
		t.Fatalf("got %+v", rows)
	}
}

func TestOverridesUpsertReplaces(t *testing.T) {
	r := overridesConn(t)
	r.Upsert("X", "first")
	if err := r.Upsert("X", "second"); err != nil {
		t.Fatalf("Upsert replace: %v", err)
	}
	rows, _ := r.List()
	if len(rows) != 1 || rows[0].IndexerID != "second" {
		t.Fatalf("upsert did not replace: %+v", rows)
	}
}

func TestOverridesDelete(t *testing.T) {
	r := overridesConn(t)
	r.Upsert("X", "y")
	if err := r.Delete("X"); err != nil {
		t.Fatalf("Delete: %v", err)
	}
	rows, _ := r.List()
	if len(rows) != 0 {
		t.Fatalf("want 0, got %d", len(rows))
	}
}

func TestOverridesAsMap(t *testing.T) {
	r := overridesConn(t)
	r.Upsert("A", "a-id")
	r.Upsert("B", "b-id")
	m, err := r.AsMap()
	if err != nil {
		t.Fatalf("AsMap: %v", err)
	}
	if m["A"] != "a-id" || m["B"] != "b-id" {
		t.Fatalf("got %+v", m)
	}
}
