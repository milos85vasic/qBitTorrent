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

func TestUpsertPatchSemanticsPreservesNilFields(t *testing.T) {
	r := freshConn(t)
	if err := r.Upsert("X", "userpass", strPtr("u"), strPtr("p"), nil); err != nil {
		t.Fatalf("Upsert initial: %v", err)
	}
	if err := r.Upsert("X", "userpass", nil, strPtr("p2"), nil); err != nil {
		t.Fatalf("Upsert patch: %v", err)
	}
	got, err := r.Get("X")
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.Username != "u" {
		t.Fatalf("nil-pointer username should preserve prior value, got %q", got.Username)
	}
	if got.Password != "p2" {
		t.Fatalf("non-nil password should update, got %q", got.Password)
	}
	if got.HasCookies {
		t.Fatalf("cookies never set, should be false")
	}
}

func TestUpsertCanToggleKind(t *testing.T) {
	r := freshConn(t)
	if err := r.Upsert("X", "userpass", strPtr("u"), strPtr("p"), nil); err != nil {
		t.Fatalf("Upsert userpass: %v", err)
	}
	if err := r.Upsert("X", "cookie", nil, nil, strPtr("c")); err != nil {
		t.Fatalf("Upsert cookie: %v", err)
	}
	got, err := r.Get("X")
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.Kind != "cookie" {
		t.Fatalf("kind not toggled, got %q", got.Kind)
	}
	if got.Cookies != "c" {
		t.Fatalf("cookies not stored, got %q", got.Cookies)
	}
}

func TestMarkUsedAdvancesTimestamp(t *testing.T) {
	r := freshConn(t)
	r.Upsert("X", "userpass", strPtr("u"), strPtr("p"), nil)
	before, _ := r.Get("X")
	if before.LastUsedAt != nil {
		t.Fatalf("LastUsedAt should be nil before MarkUsed, got %v", before.LastUsedAt)
	}
	time.Sleep(20 * time.Millisecond)
	if err := r.MarkUsed("X"); err != nil {
		t.Fatalf("MarkUsed: %v", err)
	}
	after, _ := r.Get("X")
	if after.LastUsedAt == nil {
		t.Fatalf("LastUsedAt should be set after MarkUsed")
	}
}

func TestMarkUsedReturnsNotFoundOnMissingRow(t *testing.T) {
	r := freshConn(t)
	if err := r.MarkUsed("DOES_NOT_EXIST"); err != ErrNotFound {
		t.Fatalf("want ErrNotFound, got %v", err)
	}
}

func strPtr(s string) *string { return &s }
