package repos

import (
	"path/filepath"
	"testing"

	"github.com/milos85vasic/qBitTorrent-go/internal/db"
)

func indexersConn(t *testing.T) *Indexers {
	t.Helper()
	dir := t.TempDir()
	conn, err := db.Open(filepath.Join(dir, "t.db"))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	return NewIndexers(conn)
}

func TestIndexersUpsertAndList(t *testing.T) {
	r := indexersConn(t)
	if err := r.Upsert(&Indexer{
		ID: "rutracker", DisplayName: "RuTracker.org", Type: "private",
		ConfiguredAtJackett: true, EnabledForSearch: true,
	}); err != nil {
		t.Fatalf("Upsert: %v", err)
	}
	rows, err := r.List()
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(rows) != 1 || rows[0].ID != "rutracker" {
		t.Fatalf("got %+v", rows)
	}
}

func TestIndexersDelete(t *testing.T) {
	r := indexersConn(t)
	r.Upsert(&Indexer{ID: "x", DisplayName: "X", Type: "public", EnabledForSearch: true})
	if err := r.Delete("x"); err != nil {
		t.Fatalf("Delete: %v", err)
	}
	rows, _ := r.List()
	if len(rows) != 0 {
		t.Fatalf("want 0, got %d", len(rows))
	}
}

func TestIndexersToggleEnabled(t *testing.T) {
	r := indexersConn(t)
	r.Upsert(&Indexer{ID: "x", DisplayName: "X", Type: "public", EnabledForSearch: true})
	if err := r.SetEnabled("x", false); err != nil {
		t.Fatalf("SetEnabled: %v", err)
	}
	rows, _ := r.List()
	if rows[0].EnabledForSearch {
		t.Fatal("expected disabled")
	}
}

func TestIndexersUpsertPreservesOtherFieldsOnReUpsert(t *testing.T) {
	r := indexersConn(t)
	r.Upsert(&Indexer{ID: "x", DisplayName: "X v1", Type: "public", EnabledForSearch: true})
	r.SetEnabled("x", false)
	r.Upsert(&Indexer{ID: "x", DisplayName: "X v2", Type: "public", EnabledForSearch: true})
	rows, _ := r.List()
	if rows[0].DisplayName != "X v2" {
		t.Fatalf("display_name update lost: %q", rows[0].DisplayName)
	}
	if !rows[0].EnabledForSearch {
		t.Fatalf("Upsert with EnabledForSearch=true should re-enable")
	}
}

func TestIndexersRecordTest(t *testing.T) {
	r := indexersConn(t)
	r.Upsert(&Indexer{ID: "x", DisplayName: "X", Type: "public", EnabledForSearch: true})
	if err := r.RecordTest("x", "ok"); err != nil {
		t.Fatalf("RecordTest: %v", err)
	}
	rows, _ := r.List()
	if rows[0].LastTestStatus == nil || *rows[0].LastTestStatus != "ok" {
		t.Fatalf("LastTestStatus not recorded: %+v", rows[0].LastTestStatus)
	}
	if rows[0].LastTestAt == nil {
		t.Fatalf("LastTestAt should be set")
	}
}
