package repos

import (
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"
)

// CatalogEntry mirrors a row in the catalog_cache table.
// TemplateFieldsJSON is the raw JSON returned by Jackett's
// /api/v2.0/indexers/{id}/config endpoint.
type CatalogEntry struct {
	ID                 string
	DisplayName        string
	Type               string
	Language           *string
	Description        *string
	TemplateFieldsJSON string
	CachedAt           time.Time
}

// CatalogQuery is the parameter set for Query. All filters are AND'd.
// Search is a substring (LIKE %x%) match against display_name + id +
// description (case-insensitive). Limit defaults to 50; Offset to 0.
type CatalogQuery struct {
	Search   *string
	Type     *string
	Language *string
	Limit    int
	Offset   int
}

// Catalog is the catalog_cache repo.
type Catalog struct{ conn *sql.DB }

// NewCatalog constructs a Catalog repo.
func NewCatalog(conn *sql.DB) *Catalog { return &Catalog{conn: conn} }

// Upsert inserts or replaces a single catalog entry.
func (c *Catalog) Upsert(e *CatalogEntry) error {
	_, err := c.conn.Exec(`
		INSERT INTO catalog_cache(id, display_name, type, language,
			description, template_fields_json, cached_at)
		VALUES(?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(id) DO UPDATE SET
			display_name=excluded.display_name,
			type=excluded.type,
			language=excluded.language,
			description=excluded.description,
			template_fields_json=excluded.template_fields_json,
			cached_at=excluded.cached_at
	`, e.ID, e.DisplayName, e.Type, e.Language, e.Description,
		e.TemplateFieldsJSON, e.CachedAt)
	return err
}

// Get returns one entry or ErrNotFound.
func (c *Catalog) Get(id string) (*CatalogEntry, error) {
	row := c.conn.QueryRow(`SELECT id, display_name, type, language, description,
		template_fields_json, cached_at FROM catalog_cache WHERE id=?`, id)
	e := &CatalogEntry{}
	if err := row.Scan(&e.ID, &e.DisplayName, &e.Type, &e.Language, &e.Description,
		&e.TemplateFieldsJSON, &e.CachedAt); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, err
	}
	return e, nil
}

// Query returns paginated results + total row count matching the filters.
// Default Limit=50 if zero/negative; capped at 200.
func (c *Catalog) Query(q CatalogQuery) (rows []*CatalogEntry, total int, err error) {
	if q.Limit <= 0 {
		q.Limit = 50
	}
	if q.Limit > 200 {
		q.Limit = 200
	}
	if q.Offset < 0 {
		q.Offset = 0
	}

	var (
		where []string
		args  []any
	)
	if q.Search != nil && *q.Search != "" {
		like := "%" + strings.ToLower(*q.Search) + "%"
		where = append(where, "(LOWER(display_name) LIKE ? OR LOWER(id) LIKE ? OR LOWER(COALESCE(description,'')) LIKE ?)")
		args = append(args, like, like, like)
	}
	if q.Type != nil && *q.Type != "" {
		where = append(where, "type=?")
		args = append(args, *q.Type)
	}
	if q.Language != nil && *q.Language != "" {
		where = append(where, "language=?")
		args = append(args, *q.Language)
	}

	whereClause := ""
	if len(where) > 0 {
		whereClause = " WHERE " + strings.Join(where, " AND ")
	}

	// total
	if err = c.conn.QueryRow("SELECT COUNT(*) FROM catalog_cache"+whereClause, args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count: %w", err)
	}

	// page
	pageArgs := append(args, q.Limit, q.Offset)
	r, err := c.conn.Query(`SELECT id, display_name, type, language, description,
		template_fields_json, cached_at FROM catalog_cache`+whereClause+
		` ORDER BY display_name LIMIT ? OFFSET ?`, pageArgs...)
	if err != nil {
		return nil, 0, fmt.Errorf("query: %w", err)
	}
	defer r.Close()
	for r.Next() {
		e := &CatalogEntry{}
		if err := r.Scan(&e.ID, &e.DisplayName, &e.Type, &e.Language, &e.Description,
			&e.TemplateFieldsJSON, &e.CachedAt); err != nil {
			return nil, 0, fmt.Errorf("scan: %w", err)
		}
		rows = append(rows, e)
	}
	if err := r.Err(); err != nil {
		return nil, 0, fmt.Errorf("iter: %w", err)
	}
	return rows, total, nil
}

// OlderThan returns IDs of entries with cached_at < cutoff. Used by the
// TTL refresh path (Task 18) to identify stale catalog rows.
func (c *Catalog) OlderThan(cutoff time.Time) ([]string, error) {
	rows, err := c.conn.Query("SELECT id FROM catalog_cache WHERE cached_at < ?", cutoff)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		out = append(out, id)
	}
	return out, rows.Err()
}

// ReplaceAll truncates the table and bulk-inserts the given entries in
// one transaction. Used by full-catalog refresh (Task 18).
func (c *Catalog) ReplaceAll(entries []*CatalogEntry) error {
	tx, err := c.conn.Begin()
	if err != nil {
		return fmt.Errorf("begin: %w", err)
	}
	if _, err := tx.Exec("DELETE FROM catalog_cache"); err != nil {
		tx.Rollback()
		return fmt.Errorf("truncate: %w", err)
	}
	stmt, err := tx.Prepare(`INSERT INTO catalog_cache(id, display_name, type, language,
		description, template_fields_json, cached_at) VALUES(?, ?, ?, ?, ?, ?, ?)`)
	if err != nil {
		tx.Rollback()
		return fmt.Errorf("prepare: %w", err)
	}
	defer stmt.Close()
	for _, e := range entries {
		if _, err := stmt.Exec(e.ID, e.DisplayName, e.Type, e.Language, e.Description,
			e.TemplateFieldsJSON, e.CachedAt); err != nil {
			tx.Rollback()
			return fmt.Errorf("insert %s: %w", e.ID, err)
		}
	}
	return tx.Commit()
}
