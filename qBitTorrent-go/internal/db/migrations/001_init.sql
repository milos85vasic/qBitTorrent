CREATE TABLE credentials (
  name              TEXT PRIMARY KEY,
  kind              TEXT NOT NULL CHECK (kind IN ('userpass', 'cookie')),
  username_enc      BLOB,
  password_enc      BLOB,
  cookies_enc       BLOB,
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_used_at      DATETIME
);

CREATE TABLE indexers (
  id                       TEXT PRIMARY KEY,
  display_name             TEXT NOT NULL,
  type                     TEXT NOT NULL,
  configured_at_jackett    INTEGER NOT NULL,
  linked_credential_name   TEXT REFERENCES credentials(name) ON DELETE SET NULL,
  enabled_for_search       INTEGER NOT NULL DEFAULT 1,
  last_jackett_sync_at     DATETIME,
  last_test_status         TEXT,
  last_test_at             DATETIME
);
CREATE INDEX idx_indexers_linked_cred ON indexers(linked_credential_name);

CREATE TABLE catalog_cache (
  id                    TEXT PRIMARY KEY,
  display_name          TEXT NOT NULL,
  type                  TEXT NOT NULL,
  language              TEXT,
  description           TEXT,
  template_fields_json  TEXT NOT NULL,
  cached_at             DATETIME NOT NULL
);
CREATE INDEX idx_catalog_cached_at ON catalog_cache(cached_at);

CREATE TABLE autoconfig_runs (
  id                       INTEGER PRIMARY KEY AUTOINCREMENT,
  ran_at                   DATETIME NOT NULL,
  discovered_count         INTEGER NOT NULL,
  configured_now_count     INTEGER NOT NULL,
  errors_json              TEXT NOT NULL DEFAULT '[]',
  result_summary_json      TEXT NOT NULL
);
CREATE INDEX idx_runs_ran_at ON autoconfig_runs(ran_at DESC);

CREATE TABLE indexer_map_overrides (
  env_name      TEXT PRIMARY KEY,
  indexer_id    TEXT NOT NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schema_migrations (
  version       INTEGER PRIMARY KEY,
  applied_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO schema_migrations (version) VALUES (1);
