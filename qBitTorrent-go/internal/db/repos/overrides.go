package repos

import (
	"database/sql"
	"fmt"
	"time"
)

// Override mirrors a row in indexer_map_overrides.
type Override struct {
	EnvName   string
	IndexerID string
	CreatedAt time.Time
}

// Overrides is the indexer_map_overrides repo. Replaces the
// JACKETT_INDEXER_MAP env var with persistent storage.
type Overrides struct{ conn *sql.DB }

// NewOverrides constructs an Overrides repo.
func NewOverrides(conn *sql.DB) *Overrides { return &Overrides{conn: conn} }

// Upsert inserts or replaces an override mapping env_name → indexer_id.
func (o *Overrides) Upsert(envName, indexerID string) error {
	_, err := o.conn.Exec(`INSERT INTO indexer_map_overrides(env_name, indexer_id, created_at)
		VALUES(?, ?, ?)
		ON CONFLICT(env_name) DO UPDATE SET indexer_id=excluded.indexer_id`,
		envName, indexerID, time.Now().UTC())
	if err != nil {
		return fmt.Errorf("upsert override: %w", err)
	}
	return nil
}

// List returns all overrides ordered by env_name.
func (o *Overrides) List() ([]*Override, error) {
	rows, err := o.conn.Query(`SELECT env_name, indexer_id, created_at FROM indexer_map_overrides ORDER BY env_name`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Override
	for rows.Next() {
		ov := &Override{}
		if err := rows.Scan(&ov.EnvName, &ov.IndexerID, &ov.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, ov)
	}
	return out, rows.Err()
}

// AsMap returns the overrides as a map for fast lookup by autoconfig matcher.
func (o *Overrides) AsMap() (map[string]string, error) {
	rows, err := o.List()
	if err != nil {
		return nil, err
	}
	m := make(map[string]string, len(rows))
	for _, r := range rows {
		m[r.EnvName] = r.IndexerID
	}
	return m, nil
}

// Delete removes an override. Idempotent (no error on missing row).
func (o *Overrides) Delete(envName string) error {
	_, err := o.conn.Exec("DELETE FROM indexer_map_overrides WHERE env_name=?", envName)
	return err
}
