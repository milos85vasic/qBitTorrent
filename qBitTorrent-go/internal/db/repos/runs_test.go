package repos

import (
	"path/filepath"
	"testing"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/db"
)

func runsConn(t *testing.T) *Runs {
	t.Helper()
	dir := t.TempDir()
	conn, err := db.Open(filepath.Join(dir, "t.db"))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	return NewRuns(conn)
}

func TestRunsInsertGetList(t *testing.T) {
	r := runsConn(t)
	id, err := r.Insert(&Run{
		RanAt:              time.Now().UTC(),
		DiscoveredCount:    4,
		ConfiguredNowCount: 2,
		ErrorsJSON:         `["indexer_config_failed:iptorrents:..."]`,
		ResultSummaryJSON:  `{"discovered":["RUTRACKER","IPTORRENTS"]}`,
	})
	if err != nil {
		t.Fatalf("Insert: %v", err)
	}
	if id <= 0 {
		t.Fatalf("want id>0, got %d", id)
	}
	got, err := r.Get(id)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.DiscoveredCount != 4 || got.ConfiguredNowCount != 2 {
		t.Fatalf("bad row: %+v", got)
	}
	rows, err := r.List(10)
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(rows) != 1 {
		t.Fatalf("want 1 row, got %d", len(rows))
	}
}

func TestRunsListOrderedDesc(t *testing.T) {
	r := runsConn(t)
	t1 := time.Now().UTC().Add(-2 * time.Hour)
	t2 := time.Now().UTC().Add(-1 * time.Hour)
	t3 := time.Now().UTC()
	r.Insert(&Run{RanAt: t1, ResultSummaryJSON: "{}"})
	r.Insert(&Run{RanAt: t3, ResultSummaryJSON: "{}"})
	r.Insert(&Run{RanAt: t2, ResultSummaryJSON: "{}"})
	rows, _ := r.List(10)
	if len(rows) != 3 {
		t.Fatalf("want 3, got %d", len(rows))
	}
	if !rows[0].RanAt.After(rows[1].RanAt) || !rows[1].RanAt.After(rows[2].RanAt) {
		t.Fatalf("not desc-ordered by ran_at: %+v", rows)
	}
}

func TestRunsListLimit(t *testing.T) {
	r := runsConn(t)
	for i := 0; i < 5; i++ {
		r.Insert(&Run{RanAt: time.Now().UTC().Add(time.Duration(i) * time.Second), ResultSummaryJSON: "{}"})
	}
	rows, _ := r.List(2)
	if len(rows) != 2 {
		t.Fatalf("want 2, got %d", len(rows))
	}
}

func TestRunsGetMissingErrNotFound(t *testing.T) {
	r := runsConn(t)
	if _, err := r.Get(999); err != ErrNotFound {
		t.Fatalf("want ErrNotFound, got %v", err)
	}
}
