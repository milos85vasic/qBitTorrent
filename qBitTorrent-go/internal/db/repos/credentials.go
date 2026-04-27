// Package repos provides typed CRUD over the boba SQLite tables.
// Each repo type wraps a *sql.DB and (where credentials are stored)
// the AES-256 master key.
package repos

import (
	"database/sql"
	"errors"
	"fmt"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/db"
)

// Credential is the decrypted view of a credentials row. List() returns
// these with HasUsername/HasPassword/HasCookies set but Username/Password/
// Cookies left empty (no decrypt). Get() returns the decrypted values.
type Credential struct {
	Name        string
	Kind        string
	Username    string
	Password    string
	Cookies     string
	HasUsername bool
	HasPassword bool
	HasCookies  bool
	CreatedAt   time.Time
	UpdatedAt   time.Time
	LastUsedAt  *time.Time
}

// Credentials is the credentials-table repo.
type Credentials struct {
	conn *sql.DB
	key  []byte
}

// ErrNotFound is returned by Get when no row matches.
var ErrNotFound = errors.New("repos: credential not found")

// NewCredentials constructs a Credentials repo. key must be 32 bytes
// (AES-256). Storing the key in the repo is intentional — the alternative
// (passing on every call) leaks the secret across more layers.
func NewCredentials(conn *sql.DB, key []byte) *Credentials {
	return &Credentials{conn: conn, key: key}
}

// Upsert inserts or updates a credential. Nil/empty user/pass/cookies
// fields are NOT overwritten (PATCH semantics — pass a nil pointer to
// leave a field unchanged). To explicitly clear a field, delete + re-add.
func (c *Credentials) Upsert(name, kind string, user, pass, cookies *string) error {
	var (
		uEnc, pEnc, cEnc []byte
		err              error
	)
	if user != nil && *user != "" {
		uEnc, err = db.Encrypt(c.key, *user)
		if err != nil {
			return fmt.Errorf("encrypt username: %w", err)
		}
	}
	if pass != nil && *pass != "" {
		pEnc, err = db.Encrypt(c.key, *pass)
		if err != nil {
			return fmt.Errorf("encrypt password: %w", err)
		}
	}
	if cookies != nil && *cookies != "" {
		cEnc, err = db.Encrypt(c.key, *cookies)
		if err != nil {
			return fmt.Errorf("encrypt cookies: %w", err)
		}
	}
	now := time.Now().UTC()
	_, err = c.conn.Exec(`
		INSERT INTO credentials(name, kind, username_enc, password_enc, cookies_enc, created_at, updated_at)
		VALUES(?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(name) DO UPDATE SET
			kind=excluded.kind,
			username_enc=COALESCE(excluded.username_enc, username_enc),
			password_enc=COALESCE(excluded.password_enc, password_enc),
			cookies_enc=COALESCE(excluded.cookies_enc, cookies_enc),
			updated_at=excluded.updated_at
	`, name, kind, uEnc, pEnc, cEnc, now, now)
	return err
}

// Get returns the decrypted credential. Returns ErrNotFound if no row exists.
func (c *Credentials) Get(name string) (*Credential, error) {
	row := c.conn.QueryRow(`SELECT name, kind, username_enc, password_enc, cookies_enc,
		created_at, updated_at, last_used_at FROM credentials WHERE name=?`, name)
	cr := &Credential{}
	var uEnc, pEnc, cEnc []byte
	if err := row.Scan(&cr.Name, &cr.Kind, &uEnc, &pEnc, &cEnc,
		&cr.CreatedAt, &cr.UpdatedAt, &cr.LastUsedAt); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrNotFound
		}
		return nil, fmt.Errorf("scan: %w", err)
	}
	if uEnc != nil {
		s, err := db.Decrypt(c.key, uEnc)
		if err != nil {
			return nil, fmt.Errorf("decrypt username: %w", err)
		}
		cr.Username = s
		cr.HasUsername = true
	}
	if pEnc != nil {
		s, err := db.Decrypt(c.key, pEnc)
		if err != nil {
			return nil, fmt.Errorf("decrypt password: %w", err)
		}
		cr.Password = s
		cr.HasPassword = true
	}
	if cEnc != nil {
		s, err := db.Decrypt(c.key, cEnc)
		if err != nil {
			return nil, fmt.Errorf("decrypt cookies: %w", err)
		}
		cr.Cookies = s
		cr.HasCookies = true
	}
	return cr, nil
}

// List returns all credentials with metadata only — values not decrypted.
// Use Get for decrypted values.
func (c *Credentials) List() ([]*Credential, error) {
	rows, err := c.conn.Query(`SELECT name, kind, username_enc IS NOT NULL,
		password_enc IS NOT NULL, cookies_enc IS NOT NULL,
		created_at, updated_at, last_used_at FROM credentials ORDER BY name`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Credential
	for rows.Next() {
		cr := &Credential{}
		if err := rows.Scan(&cr.Name, &cr.Kind, &cr.HasUsername, &cr.HasPassword, &cr.HasCookies,
			&cr.CreatedAt, &cr.UpdatedAt, &cr.LastUsedAt); err != nil {
			return nil, err
		}
		out = append(out, cr)
	}
	return out, rows.Err()
}

// Delete removes a credential. No error if the row didn't exist (idempotent).
func (c *Credentials) Delete(name string) error {
	_, err := c.conn.Exec("DELETE FROM credentials WHERE name=?", name)
	return err
}

// MarkUsed updates last_used_at on the named row. Used after autoconfig
// successfully applies the credential to a Jackett indexer.
func (c *Credentials) MarkUsed(name string) error {
	_, err := c.conn.Exec("UPDATE credentials SET last_used_at=CURRENT_TIMESTAMP WHERE name=?", name)
	return err
}
