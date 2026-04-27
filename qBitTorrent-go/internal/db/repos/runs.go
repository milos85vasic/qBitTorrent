package repos

import (
	"database/sql"
	"errors"
	"fmt"
	"time"
)

// Run mirrors a row in autoconfig_runs.
type Run struct {
	ID                 int64
	RanAt              time.Time
	DiscoveredCount    int
	ConfiguredNowCount int
	ErrorsJSON         string
	ResultSummaryJSON  string
}

// Runs is the autoconfig_runs repo.
type Runs struct{ conn *sql.DB }

// NewRuns constructs a Runs repo.
func NewRuns(conn *sql.DB) *Runs { return &Runs{conn: conn} }

// Insert records an autoconfig run. Returns the new row id.
// ErrorsJSON defaults to "[]" if empty (to satisfy NOT NULL DEFAULT).
func (r *Runs) Insert(run *Run) (int64, error) {
	errs := run.ErrorsJSON
	if errs == "" {
		errs = "[]"
	}
	res, err := r.conn.Exec(`INSERT INTO autoconfig_runs(ran_at, discovered_count,
		configured_now_count, errors_json, result_summary_json)
		VALUES(?, ?, ?, ?, ?)`,
		run.RanAt, run.DiscoveredCount, run.ConfiguredNowCount, errs, run.ResultSummaryJSON)
	if err != nil {
		return 0, fmt.Errorf("insert run: %w", err)
	}
	return res.LastInsertId()
}

// Get returns the run by id, or ErrNotFound.
func (r *Runs) Get(id int64) (*Run, error) {
	row := r.conn.QueryRow(`SELECT id, ran_at, discovered_count, configured_now_count,
		errors_json, result_summary_json FROM autoconfig_runs WHERE id=?`, id)
	out := &Run{}
	if err := row.Scan(&out.ID, &out.RanAt, &out.DiscoveredCount, &out.ConfiguredNowCount,
		&out.ErrorsJSON, &out.ResultSummaryJSON); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	return out, nil
}

// List returns up to limit runs, most recent first.
func (r *Runs) List(limit int) ([]*Run, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := r.conn.Query(`SELECT id, ran_at, discovered_count, configured_now_count,
		errors_json, result_summary_json FROM autoconfig_runs ORDER BY ran_at DESC, id DESC LIMIT ?`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Run
	for rows.Next() {
		run := &Run{}
		if err := rows.Scan(&run.ID, &run.RanAt, &run.DiscoveredCount, &run.ConfiguredNowCount,
			&run.ErrorsJSON, &run.ResultSummaryJSON); err != nil {
			return nil, err
		}
		out = append(out, run)
	}
	return out, rows.Err()
}
