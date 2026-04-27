package repos

import (
	"crypto/rand"
	"path/filepath"
	"testing"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/db"
)

func freshConn(t *testing.T) *Credentials {
	t.Helper()
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
	return NewCredentials(conn, key)
}

func TestUpsertAndGet(t *testing.T) {
	r := freshConn(t)
	if err := r.Upsert("RUTRACKER", "userpass", strPtr("u"), strPtr("p"), nil); err != nil {
		t.Fatalf("Upsert: %v", err)
	}
	got, err := r.Get("RUTRACKER")
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.Name != "RUTRACKER" || got.Kind != "userpass" {
		t.Fatalf("bad row: %+v", got)
	}
	if got.Username != "u" || got.Password != "p" {
		t.Fatalf("decrypt mismatch: %+v", got)
	}
}

func TestList(t *testing.T) {
	r := freshConn(t)
	r.Upsert("RUTRACKER", "userpass", strPtr("u"), strPtr("p"), nil)
	r.Upsert("IPTORRENTS", "cookie", nil, nil, strPtr("c"))
	rows, err := r.List()
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(rows) != 2 {
		t.Fatalf("want 2 rows, got %d", len(rows))
	}
}

func TestDelete(t *testing.T) {
	r := freshConn(t)
	r.Upsert("X", "userpass", strPtr("u"), strPtr("p"), nil)
	if err := r.Delete("X"); err != nil {
		t.Fatalf("Delete: %v", err)
	}
	_, err := r.Get("X")
	if err == nil {
		t.Fatal("expected not-found")
	}
}

func TestUpsertOverwritesUpdatedAt(t *testing.T) {
	r := freshConn(t)
	r.Upsert("X", "userpass", strPtr("u"), strPtr("p"), nil)
	first, _ := r.Get("X")
	time.Sleep(1100 * time.Millisecond)
	r.Upsert("X", "userpass", strPtr("u2"), strPtr("p2"), nil)
	second, _ := r.Get("X")
	if !second.UpdatedAt.After(first.UpdatedAt) {
		t.Fatalf("updated_at did not advance: %v then %v", first.UpdatedAt, second.UpdatedAt)
	}
}

func strPtr(s string) *string { return &s }
