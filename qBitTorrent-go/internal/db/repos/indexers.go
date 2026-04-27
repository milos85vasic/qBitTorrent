package repos

import (
	"database/sql"
	"time"
)

// Indexer mirrors a row in the indexers table.
type Indexer struct {
	ID                   string
	DisplayName          string
	Type                 string // "public" | "private" | "semi-private"
	ConfiguredAtJackett  bool
	LinkedCredentialName *string // nullable FK to credentials(name)
	EnabledForSearch     bool
	LastJackettSyncAt    *time.Time
	LastTestStatus       *string // "ok" | "auth_failed" | "unreachable" | "empty_results" | nil
	LastTestAt           *time.Time
}

// Indexers is the indexers-table repo.
type Indexers struct{ conn *sql.DB }

// NewIndexers constructs an Indexers repo.
func NewIndexers(conn *sql.DB) *Indexers { return &Indexers{conn: conn} }

// Upsert inserts or replaces an indexer row. All fields on the struct are
// applied verbatim (no PATCH semantics — this is a full mirror of the
// indexer's current state, refreshed by autoconfig + UI actions).
func (r *Indexers) Upsert(i *Indexer) error {
	_, err := r.conn.Exec(`
		INSERT INTO indexers(id, display_name, type, configured_at_jackett,
			linked_credential_name, enabled_for_search, last_jackett_sync_at,
			last_test_status, last_test_at)
		VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(id) DO UPDATE SET
			display_name=excluded.display_name,
			type=excluded.type,
			configured_at_jackett=excluded.configured_at_jackett,
			linked_credential_name=excluded.linked_credential_name,
			enabled_for_search=excluded.enabled_for_search,
			last_jackett_sync_at=excluded.last_jackett_sync_at,
			last_test_status=excluded.last_test_status,
			last_test_at=excluded.last_test_at
	`, i.ID, i.DisplayName, i.Type, i.ConfiguredAtJackett,
		i.LinkedCredentialName, i.EnabledForSearch, i.LastJackettSyncAt,
		i.LastTestStatus, i.LastTestAt)
	return err
}

// List returns all indexers ordered by id.
func (r *Indexers) List() ([]*Indexer, error) {
	rows, err := r.conn.Query(`SELECT id, display_name, type, configured_at_jackett,
		linked_credential_name, enabled_for_search, last_jackett_sync_at,
		last_test_status, last_test_at FROM indexers ORDER BY id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Indexer
	for rows.Next() {
		i := &Indexer{}
		if err := rows.Scan(&i.ID, &i.DisplayName, &i.Type, &i.ConfiguredAtJackett,
			&i.LinkedCredentialName, &i.EnabledForSearch, &i.LastJackettSyncAt,
			&i.LastTestStatus, &i.LastTestAt); err != nil {
			return nil, err
		}
		out = append(out, i)
	}
	return out, rows.Err()
}

// Delete removes an indexer row. Idempotent.
func (r *Indexers) Delete(id string) error {
	_, err := r.conn.Exec("DELETE FROM indexers WHERE id=?", id)
	return err
}

// SetEnabled toggles enabled_for_search WITHOUT touching other fields.
// Returns ErrNotFound if no row matches.
func (r *Indexers) SetEnabled(id string, enabled bool) error {
	res, err := r.conn.Exec("UPDATE indexers SET enabled_for_search=? WHERE id=?", enabled, id)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		return ErrNotFound
	}
	return nil
}

// RecordTest stamps last_test_status and last_test_at. Returns ErrNotFound
// if no row matches.
func (r *Indexers) RecordTest(id, status string) error {
	res, err := r.conn.Exec("UPDATE indexers SET last_test_status=?, last_test_at=? WHERE id=?",
		status, time.Now().UTC(), id)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		return ErrNotFound
	}
	return nil
}
