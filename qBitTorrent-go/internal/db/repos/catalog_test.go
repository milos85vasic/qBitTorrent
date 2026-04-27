package repos

import (
	"path/filepath"
	"testing"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/db"
)

func catalogConn(t *testing.T) *Catalog {
	t.Helper()
	dir := t.TempDir()
	conn, err := db.Open(filepath.Join(dir, "t.db"))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	return NewCatalog(conn)
}

func makeEntry(id, name, typ, lang string) *CatalogEntry {
	return &CatalogEntry{
		ID:                 id,
		DisplayName:        name,
		Type:               typ,
		Language:           strPtr(lang),
		Description:        strPtr("desc for " + id),
		TemplateFieldsJSON: `[{"id":"username","type":"inputstring"}]`,
		CachedAt:           time.Now().UTC(),
	}
}

func TestCatalogUpsertGet(t *testing.T) {
	r := catalogConn(t)
	if err := r.Upsert(makeEntry("rutracker", "RuTracker.org", "private", "ru")); err != nil {
		t.Fatalf("Upsert: %v", err)
	}
	e, err := r.Get("rutracker")
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if e.DisplayName != "RuTracker.org" || e.Type != "private" {
		t.Fatalf("bad row: %+v", e)
	}
}

func TestCatalogQueryFilters(t *testing.T) {
	r := catalogConn(t)
	r.Upsert(makeEntry("rutracker", "RuTracker.org", "private", "ru"))
	r.Upsert(makeEntry("kinozal", "Kinozal", "private", "ru"))
	r.Upsert(makeEntry("piratebay", "The Pirate Bay", "public", "en"))
	r.Upsert(makeEntry("eztv", "EZTV", "public", "en"))

	cases := []struct {
		name string
		q    CatalogQuery
		want int
	}{
		{"all (no filter)", CatalogQuery{Limit: 100}, 4},
		{"type=private", CatalogQuery{Type: strPtr("private"), Limit: 100}, 2},
		{"type=public", CatalogQuery{Type: strPtr("public"), Limit: 100}, 2},
		{"language=ru", CatalogQuery{Language: strPtr("ru"), Limit: 100}, 2},
		{"search rutra", CatalogQuery{Search: strPtr("rutra"), Limit: 100}, 1},
		{"search bay", CatalogQuery{Search: strPtr("bay"), Limit: 100}, 1},
		// 'kino' uniquely matches kinozal — 'k' alone matches both because
		// "rutracker" id/description also contains the letter 'k'.
		{"combined: private + ru + 'kino'", CatalogQuery{Type: strPtr("private"), Language: strPtr("ru"), Search: strPtr("kino"), Limit: 100}, 1},
		{"limit 1", CatalogQuery{Limit: 1}, 1},
		{"limit 2 offset 1", CatalogQuery{Limit: 2, Offset: 1}, 2},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			rows, total, err := r.Query(tc.q)
			if err != nil {
				t.Fatalf("Query: %v", err)
			}
			if len(rows) != tc.want {
				t.Fatalf("got %d rows, want %d (rows=%+v total=%d)", len(rows), tc.want, rows, total)
			}
		})
	}
}

func TestCatalogQueryReturnsTotal(t *testing.T) {
	r := catalogConn(t)
	for i, id := range []string{"a", "b", "c", "d", "e"} {
		_ = i
		r.Upsert(makeEntry(id, id, "public", "en"))
	}
	rows, total, err := r.Query(CatalogQuery{Limit: 2})
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if len(rows) != 2 {
		t.Fatalf("got %d rows, want 2", len(rows))
	}
	if total != 5 {
		t.Fatalf("got total %d, want 5", total)
	}
}

func TestCatalogOlderThan(t *testing.T) {
	r := catalogConn(t)
	now := time.Now().UTC()
	old := makeEntry("old", "Old", "public", "en")
	old.CachedAt = now.Add(-2 * time.Hour)
	r.Upsert(old)
	r.Upsert(makeEntry("new", "New", "public", "en"))

	stale, err := r.OlderThan(now.Add(-1 * time.Hour))
	if err != nil {
		t.Fatalf("OlderThan: %v", err)
	}
	if len(stale) != 1 || stale[0] != "old" {
		t.Fatalf("want [old], got %+v", stale)
	}
}

func TestCatalogReplaceAll(t *testing.T) {
	r := catalogConn(t)
	r.Upsert(makeEntry("a", "A", "public", "en"))
	r.Upsert(makeEntry("b", "B", "public", "en"))

	if err := r.ReplaceAll([]*CatalogEntry{makeEntry("c", "C", "public", "en")}); err != nil {
		t.Fatalf("ReplaceAll: %v", err)
	}
	rows, _, _ := r.Query(CatalogQuery{Limit: 100})
	if len(rows) != 1 || rows[0].ID != "c" {
		t.Fatalf("want [c], got %+v", rows)
	}
}

func TestCatalogReplaceAllRejectsEmpty(t *testing.T) {
	r := catalogConn(t)
	r.Upsert(makeEntry("a", "A", "public", "en"))
	if err := r.ReplaceAll(nil); err == nil {
		t.Fatal("ReplaceAll(nil) should error")
	}
	if err := r.ReplaceAll([]*CatalogEntry{}); err == nil {
		t.Fatal("ReplaceAll([]) should error")
	}
	rows, _, _ := r.Query(CatalogQuery{Limit: 100})
	if len(rows) != 1 {
		t.Fatalf("rows must survive empty ReplaceAll attempts; got %d", len(rows))
	}
}

func TestCatalogQueryDeterministicOrderOnNameTie(t *testing.T) {
	r := catalogConn(t)
	// Two entries with IDENTICAL display_name but different ids — pagination
	// must not silently drop or duplicate either across page boundaries.
	r.Upsert(makeEntry("aaa", "Same Name", "public", "en"))
	r.Upsert(makeEntry("bbb", "Same Name", "public", "en"))
	r.Upsert(makeEntry("ccc", "Same Name", "public", "en"))

	page1, _, _ := r.Query(CatalogQuery{Limit: 2, Offset: 0})
	page2, _, _ := r.Query(CatalogQuery{Limit: 2, Offset: 2})
	seen := map[string]bool{}
	for _, row := range append(page1, page2...) {
		if seen[row.ID] {
			t.Fatalf("duplicate id %q across pages", row.ID)
		}
		seen[row.ID] = true
	}
	if len(seen) != 3 {
		t.Fatalf("expected 3 unique rows across pages, got %d", len(seen))
	}
}
