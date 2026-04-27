package repos

import (
	"crypto/rand"
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

func TestFKDeleteCredentialNullsLinkedIndexer(t *testing.T) {
	// Wire BOTH repos onto the same connection so they share state.
	dir := t.TempDir()
	conn, err := db.Open(filepath.Join(dir, "t.db"))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	key := make([]byte, 32)
	rand.Read(key)
	creds := NewCredentials(conn, key)
	idx := NewIndexers(conn)

	// Insert credential, then indexer linking to it.
	if err := creds.Upsert("RUTRACKER", "userpass", strPtr("u"), strPtr("p"), nil); err != nil {
		t.Fatalf("creds.Upsert: %v", err)
	}
	link := "RUTRACKER"
	if err := idx.Upsert(&Indexer{
		ID: "rutracker", DisplayName: "RuTracker", Type: "private",
		ConfiguredAtJackett: true, EnabledForSearch: true,
		LinkedCredentialName: &link,
	}); err != nil {
		t.Fatalf("idx.Upsert: %v", err)
	}

	// Sanity: the link is set.
	rows, _ := idx.List()
	if rows[0].LinkedCredentialName == nil || *rows[0].LinkedCredentialName != "RUTRACKER" {
		t.Fatalf("link not set pre-delete: %+v", rows[0].LinkedCredentialName)
	}

	// Delete the credential — FK ON DELETE SET NULL should null the indexer's link.
	if err := creds.Delete("RUTRACKER"); err != nil {
		t.Fatalf("creds.Delete: %v", err)
	}

	// Verify the indexer row still exists with linked_credential_name now NULL.
	rows, _ = idx.List()
	if len(rows) != 1 {
		t.Fatalf("indexer row should still exist; got %d rows", len(rows))
	}
	if rows[0].LinkedCredentialName != nil {
		t.Fatalf("FK ON DELETE SET NULL did not fire — link still %q", *rows[0].LinkedCredentialName)
	}
}
