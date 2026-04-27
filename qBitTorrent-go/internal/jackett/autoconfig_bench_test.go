package jackett

import (
	"crypto/rand"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"github.com/milos85vasic/qBitTorrent-go/internal/db"
	"github.com/milos85vasic/qBitTorrent-go/internal/db/repos"
)

// BenchmarkAutoconfigFullRun covers spec §10.5: one full autoconfig
// pass with 5 mock indexers (no real Jackett — httptest.NewServer
// provides /api/v2.0/indexers + /config endpoints). Target p99 < 5s.
//
// The benchmark seeds 5 credentials and 5 fake indexers in the catalog,
// runs the orchestrator, and verifies it consumed every credential
// (sanity check; without it the benchmark would optimize against a
// no-op Autoconfigure path).
//
// Run:
//
//	GOMAXPROCS=2 nice -n 19 ionice -c 3 go test -bench=. -benchmem \
//	  -benchtime=3s ./internal/jackett/ -run=^$
func BenchmarkAutoconfigFullRun(b *testing.B) {
	// Spin up a fake Jackett.
	mux := http.NewServeMux()
	indexerIDs := []string{"rutracker", "kinozal", "iptorrents", "nnmclub", "tpb"}
	mux.HandleFunc("/api/v2.0/indexers", func(w http.ResponseWriter, r *http.Request) {
		entries := make([]CatalogEntry, 0, len(indexerIDs))
		for _, id := range indexerIDs {
			entries = append(entries, CatalogEntry{
				ID: id, Name: id, Type: "private",
				Configured: false, Language: "en",
			})
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(entries)
	})
	mux.HandleFunc("/api/v2.0/indexers/", func(w http.ResponseWriter, r *http.Request) {
		// Accept GET (template) and POST (config).
		if r.Method == http.MethodGet {
			tmpl := []map[string]any{
				{"id": "username", "type": "text", "name": "User"},
				{"id": "password", "type": "password", "name": "Pass"},
			}
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(tmpl)
			return
		}
		if r.Method == http.MethodPost {
			w.WriteHeader(200)
			return
		}
		w.WriteHeader(http.StatusMethodNotAllowed)
	})
	mux.HandleFunc("/UI/Dashboard", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(200)
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	// Each iteration uses a fresh DB so the "configured" set starts
	// empty and the orchestrator does the full configure-N work.
	envNames := []string{"RUTRACKER", "KINOZAL", "IPTORRENTS", "NNMCLUB", "TPB"}

	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		b.StopTimer()
		dir := b.TempDir()
		conn, err := db.Open(filepath.Join(dir, "bench.db"))
		if err != nil {
			b.Fatalf("Open: %v", err)
		}
		if err := db.Migrate(conn); err != nil {
			b.Fatalf("Migrate: %v", err)
		}
		key := make([]byte, 32)
		_, _ = rand.Read(key)
		credsRepo := repos.NewCredentials(conn, key)
		indexersRepo := repos.NewIndexers(conn)
		runsRepo := repos.NewRuns(conn)
		overridesRepo := repos.NewOverrides(conn)

		// Seed creds.
		for j, name := range envNames {
			u := fmt.Sprintf("u%d", j)
			p := fmt.Sprintf("p%d", j)
			if err := credsRepo.Upsert(name, "userpass", &u, &p, nil); err != nil {
				b.Fatalf("seed %s: %v", name, err)
			}
		}
		// Seed overrides so the matcher hits without fuzzy work.
		for j, name := range envNames {
			if err := overridesRepo.Upsert(name, indexerIDs[j]); err != nil {
				b.Fatalf("override %s: %v", name, err)
			}
		}

		client := NewClient(srv.URL, "bench-key")
		deps := AutoconfigDeps{
			Creds: credsRepo, Overrides: overridesRepo,
			Indexers: indexersRepo, Runs: runsRepo, Client: client,
		}
		b.StartTimer()

		result := Autoconfigure(deps, nil)

		b.StopTimer()
		if len(result.ConfiguredNow) != len(envNames) {
			b.Fatalf("benchmark failed: configured_now=%v want %d, errors=%v",
				result.ConfiguredNow, len(envNames), result.Errors)
		}
		_ = conn.Close()
		b.StartTimer()
	}
}
