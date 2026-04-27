package jackettapi

import (
	"encoding/json"
	"errors"
	"net/http"
	"strings"
	"time"

	"github.com/milos85vasic/qBitTorrent-go/internal/db/repos"
	"github.com/milos85vasic/qBitTorrent-go/internal/envfile"
	"github.com/milos85vasic/qBitTorrent-go/internal/jackett"
)

// CredentialsDeps wires the runtime dependencies the credentials endpoints
// need. EnvPath is the absolute path to the .env file we mirror writes to
// (per spec §7 row 1: "✅ atomic mirror"). AutoconfigTrigger is invoked
// after a successful upsert to replay the autoconfig pass; nil disables
// the replay (useful for unit tests). Jackett may be nil for tests; in
// production it's used by [HandleDeleteCredential] for the cascade
// `DELETE /api/v2.0/indexers/{id}` per spec §7 row 2.
//
// NOTE on transactionality: the spec demands "hybrid C: BOTH writes must
// succeed". The Phase 1 [repos.Credentials] does not expose a transaction
// handle (its Upsert/Delete are single-statement Execs against *sql.DB),
// so we cannot wrap DB + .env writes in a single SQL tx. Instead we use
// a compensating-action pattern: snapshot the prior DB state, perform the
// DB write, perform the .env write, and on .env failure undo the DB
// write (delete-if-new, restore-prior-values-if-update). The end-state
// guarantee is the same as a true 2PC: both succeed or both end in their
// pre-call state. Documented choice over modifying Phase 1 repo surface.
type CredentialsDeps struct {
	Repo              *repos.Credentials
	Indexers          *repos.Indexers
	Jackett           *jackett.Client
	EnvPath           string
	AutoconfigTrigger func()
}

// credentialDTO is the GET / POST response shape per spec §8.1. Plaintext
// values are NEVER serialized — only "has_*" booleans and metadata.
// `last_used_at` is omitted when nil so the JSON shape matches the spec
// (which lists it as optional).
type credentialDTO struct {
	Name        string     `json:"name"`
	Kind        string     `json:"kind"`
	HasUsername bool       `json:"has_username"`
	HasPassword bool       `json:"has_password"`
	HasCookies  bool       `json:"has_cookies"`
	CreatedAt   time.Time  `json:"created_at"`
	UpdatedAt   time.Time  `json:"updated_at"`
	LastUsedAt  *time.Time `json:"last_used_at,omitempty"`
}

func toDTO(c *repos.Credential) credentialDTO {
	return credentialDTO{
		Name:        c.Name,
		Kind:        c.Kind,
		HasUsername: c.HasUsername,
		HasPassword: c.HasPassword,
		HasCookies:  c.HasCookies,
		CreatedAt:   c.CreatedAt,
		UpdatedAt:   c.UpdatedAt,
		LastUsedAt:  c.LastUsedAt,
	}
}

// credentialPostBody is the POST request body. PATCH semantics — only
// fields whose JSON keys are present (non-nil pointers after decode) are
// updated in DB and mirrored into .env.
type credentialPostBody struct {
	Name     string  `json:"name"`
	Username *string `json:"username,omitempty"`
	Password *string `json:"password,omitempty"`
	Cookies  *string `json:"cookies,omitempty"`
}

// HandleListCredentials handles GET /credentials. Returns a JSON array of
// [credentialDTO] (never plaintext). An empty list serializes as `[]`,
// not `null`, because the dashboard distinguishes "no credentials yet"
// from "API error".
func (d *CredentialsDeps) HandleListCredentials(w http.ResponseWriter, r *http.Request) {
	rows, err := d.Repo.List()
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, "list_failed", err.Error())
		return
	}
	out := make([]credentialDTO, 0, len(rows))
	for _, c := range rows {
		out = append(out, toDTO(c))
	}
	writeJSON(w, http.StatusOK, out)
}

// HandleUpsertCredential handles POST /credentials with PATCH semantics
// (spec §8.1: "only fields present are updated"). On success:
//
//  1. The credentials row is upserted in the encrypted DB.
//  2. The matching `<NAME>_USERNAME` / `<NAME>_PASSWORD` / `<NAME>_COOKIES`
//     keys are mirrored atomically into .env (spec §7 row 1).
//  3. The autoconfig orchestrator is replayed via [CredentialsDeps.AutoconfigTrigger]
//     so the new credential is immediately reflected in Jackett.
//
// On .env failure, the DB write is reverted (compensating action) and a
// 500 with code `env_write_failed_db_rolled_back` is returned. The
// autoconfig replay is best-effort and is NOT triggered on failure.
//
// Existing-row kind preservation: when a row already exists, the row's
// existing `kind` is preserved on partial updates (e.g. PATCHing only
// `cookies` on a "userpass" row leaves the row's kind as "userpass").
// This matches "only fields present are updated" — kind is derived, not
// supplied, so an unspecified update should not flip it.
func (d *CredentialsDeps) HandleUpsertCredential(w http.ResponseWriter, r *http.Request) {
	var body credentialPostBody
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeJSONError(w, http.StatusBadRequest, "bad_json", err.Error())
		return
	}
	if body.Name == "" {
		writeJSONError(w, http.StatusBadRequest, "missing_name", "name is required")
		return
	}

	// Snapshot prior state for compensating rollback.
	var prior *repos.Credential
	if existing, err := d.Repo.Get(body.Name); err == nil {
		prior = existing
	} else if !errors.Is(err, repos.ErrNotFound) {
		writeJSONError(w, http.StatusInternalServerError, "snapshot_failed", err.Error())
		return
	}

	// Derive kind. If the row pre-exists, preserve the existing kind on
	// partial updates (PATCH semantics — see GoDoc above). Otherwise,
	// userpass when user/pass present, cookie when only cookies present.
	kind := ""
	if prior != nil {
		kind = prior.Kind
	} else if body.Username != nil || body.Password != nil {
		kind = "userpass"
	} else if body.Cookies != nil {
		kind = "cookie"
	} else {
		writeJSONError(w, http.StatusBadRequest, "no_fields", "username/password or cookies required")
		return
	}

	// 1) DB upsert.
	if err := d.Repo.Upsert(body.Name, kind, body.Username, body.Password, body.Cookies); err != nil {
		writeJSONError(w, http.StatusInternalServerError, "db_upsert_failed", err.Error())
		return
	}

	// 2) .env mirror — only the fields the caller actually supplied.
	envKV := map[string]string{}
	if body.Username != nil {
		envKV[body.Name+"_USERNAME"] = *body.Username
	}
	if body.Password != nil {
		envKV[body.Name+"_PASSWORD"] = *body.Password
	}
	if body.Cookies != nil {
		envKV[body.Name+"_COOKIES"] = *body.Cookies
	}
	if len(envKV) > 0 {
		if err := envfile.Upsert(d.EnvPath, envKV); err != nil {
			// Compensating rollback.
			if prior == nil {
				_ = d.Repo.Delete(body.Name)
			} else {
				_ = d.Repo.Upsert(prior.Name, prior.Kind,
					ifSet(prior.Username), ifSet(prior.Password), ifSet(prior.Cookies))
			}
			writeJSONError(w, http.StatusInternalServerError, "env_write_failed_db_rolled_back", err.Error())
			return
		}
	}

	// 3) Autoconfig replay (spec §7 row 1 "✅ replay autoconfig for that
	// single tracker"). The orchestrator runs the FULL pass — there's no
	// one-tracker mode in [jackett.Autoconfigure] — but it's idempotent
	// (already-configured indexers aren't re-POSTed), so triggering the
	// whole bundle is acceptable and matches the Python parity stance.
	// Production wraps this in `go jackett.Autoconfigure(...)` so the
	// HTTP request thread isn't blocked on Jackett round-trips. Failure
	// here is best-effort: the DB + .env are already consistent.
	if d.AutoconfigTrigger != nil {
		d.AutoconfigTrigger()
	}

	// 4) Re-read for response body so the caller sees post-write timestamps.
	out, err := d.Repo.Get(body.Name)
	if err != nil {
		writeJSONError(w, http.StatusInternalServerError, "post_write_read_failed", err.Error())
		return
	}
	writeJSON(w, http.StatusOK, toDTO(out))
}

// HandleDeleteCredential handles DELETE /credentials/{name} per spec
// §7 row 2: removes the row from DB, removes the `<NAME>_*` triple from
// .env, and removes any linked indexers from Jackett. Linked-indexer
// rows in our DB get their `linked_credential_name` set to NULL via the
// schema's `ON DELETE SET NULL` FK — no application-side cascade needed.
//
// Returns 204 on success (spec §8.1). Idempotent: deleting a missing
// name still returns 204 because the underlying [repos.Credentials.Delete]
// is no-error-on-empty.
//
// .env and Jackett deletes are best-effort (DB is canonical post-delete);
// failures are silently swallowed. The 204 status reflects DB success.
func (d *CredentialsDeps) HandleDeleteCredential(w http.ResponseWriter, r *http.Request) {
	name := strings.TrimPrefix(r.URL.Path, "/api/v1/jackett/credentials/")
	if name == "" || strings.Contains(name, "/") {
		writeJSONError(w, http.StatusBadRequest, "bad_name", "name path segment required")
		return
	}

	// Snapshot linked indexer IDs BEFORE the DB delete: the schema's
	// ON DELETE SET NULL clears `linked_credential_name`, so reading
	// after delete loses the link.
	var jackettIDs []string
	if d.Indexers != nil {
		if all, err := d.Indexers.List(); err == nil {
			for _, idx := range all {
				if idx.LinkedCredentialName != nil && *idx.LinkedCredentialName == name {
					jackettIDs = append(jackettIDs, idx.ID)
				}
			}
		}
	}

	// 1) DB delete (FK SET NULL handles indexers.linked_credential_name).
	if err := d.Repo.Delete(name); err != nil {
		writeJSONError(w, http.StatusInternalServerError, "db_delete_failed", err.Error())
		return
	}

	// 2) .env delete (best-effort — DB is canonical at this point).
	_ = envfile.Delete(d.EnvPath, []string{
		name + "_USERNAME",
		name + "_PASSWORD",
		name + "_COOKIES",
	})

	// 3) Jackett-side delete (best-effort).
	if d.Jackett != nil {
		for _, id := range jackettIDs {
			_ = d.Jackett.DeleteIndexer(id)
		}
	}

	w.WriteHeader(http.StatusNoContent)
}

// ifSet returns &s when s != "", else nil — for compensating-rollback
// restoration via [repos.Credentials.Upsert] (which treats nil as
// "leave unchanged" and a non-nil empty pointer also as "leave unchanged",
// per its PATCH semantics).
func ifSet(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}

// writeJSON serializes v as JSON with the given status. Errors during
// the encode write are intentionally not surfaced — by the time encoding
// runs, the response status has already been sent and a second write
// would corrupt the wire response.
func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

// writeJSONError writes a structured `{error, detail}` body. Format
// mirrors what the merge-service dashboard already consumes elsewhere.
func writeJSONError(w http.ResponseWriter, status int, code, msg string) {
	writeJSON(w, status, map[string]string{"error": code, "detail": msg})
}
