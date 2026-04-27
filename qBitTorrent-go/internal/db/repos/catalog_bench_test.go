package repos

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"path/filepath"
	"testing"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/db"
)

// seedBenchCatalog populates the catalog_cache table with N rows of
// representative shape (mix of types and languages so filter
// benchmarks see meaningful selectivity). Returns the live repo.
func seedBenchCatalog(b *testing.B, n int) *Catalog {
	b.Helper()
	dir := b.TempDir()
	conn, err := db.Open(filepath.Join(dir, "bench.db"))
	if err != nil {
		b.Fatalf("Open: %v", err)
	}
	b.Cleanup(func() { _ = conn.Close() })
	if err := db.Migrate(conn); err != nil {
		b.Fatalf("Migrate: %v", err)
	}
	c := NewCatalog(conn)

	types := []string{"public", "private", "semi-private"}
	langs := []string{"en", "ru", "es", "de", "fr"}
	now := time.Now().UTC()
	rows := make([]*CatalogEntry, 0, n)
	for i := 0; i < n; i++ {
		// Generate a unique-but-prefix-stable id so substring search
		// finds many hits ("idx-…").
		raw := make([]byte, 4)
		_, _ = rand.Read(raw)
		id := fmt.Sprintf("idx-%04d-%s", i, hex.EncodeToString(raw))
		lang := langs[i%len(langs)]
		typ := types[i%len(types)]
		desc := fmt.Sprintf("Indexer %d for benchmarks (%s/%s)", i, lang, typ)
		rows = append(rows, &CatalogEntry{
			ID:                 id,
			DisplayName:        fmt.Sprintf("Indexer %04d", i),
			Type:               typ,
			Language:           &lang,
			Description:        &desc,
			TemplateFieldsJSON: `[{"id":"username","type":"text","name":"User"},{"id":"password","type":"password","name":"Pass"}]`,
			CachedAt:           now,
		})
	}
	if err := c.ReplaceAll(rows); err != nil {
		b.Fatalf("seed ReplaceAll: %v", err)
	}
	return c
}

// BenchmarkCatalogQuery covers spec §10.5 first benchmark: query a 620-row
// catalog cache under four filter combinations. Target p99 < 50ms.
//
// Run:
//
//	GOMAXPROCS=2 nice -n 19 ionice -c 3 go test -bench=. -benchmem \
//	  -benchtime=3s ./internal/db/repos/ -run=^$
func BenchmarkCatalogQuery(b *testing.B) {
	c := seedBenchCatalog(b, 620)

	b.Run("no_filter", func(b *testing.B) {
		b.ReportAllocs()
		for i := 0; i < b.N; i++ {
			rows, total, err := c.Query(CatalogQuery{Limit: 50})
			if err != nil {
				b.Fatalf("Query: %v", err)
			}
			if total != 620 || len(rows) != 50 {
				b.Fatalf("unexpected: total=%d rows=%d", total, len(rows))
			}
		}
	})

	b.Run("text_search_3char", func(b *testing.B) {
		b.ReportAllocs()
		s := "idx" // matches every id (substring)
		for i := 0; i < b.N; i++ {
			_, total, err := c.Query(CatalogQuery{Search: &s, Limit: 50})
			if err != nil {
				b.Fatalf("Query: %v", err)
			}
			if total < 100 {
				b.Fatalf("text search returned %d rows", total)
			}
		}
	})

	b.Run("type_filter", func(b *testing.B) {
		b.ReportAllocs()
		t := "private"
		for i := 0; i < b.N; i++ {
			_, total, err := c.Query(CatalogQuery{Type: &t, Limit: 50})
			if err != nil {
				b.Fatalf("Query: %v", err)
			}
			if total < 100 {
				b.Fatalf("type filter returned %d", total)
			}
		}
	})

	b.Run("text_plus_language", func(b *testing.B) {
		b.ReportAllocs()
		s := "idx"
		l := "ru"
		for i := 0; i < b.N; i++ {
			_, total, err := c.Query(CatalogQuery{Search: &s, Language: &l, Limit: 50})
			if err != nil {
				b.Fatalf("Query: %v", err)
			}
			if total < 50 {
				b.Fatalf("combined filter returned %d", total)
			}
		}
	})
}
