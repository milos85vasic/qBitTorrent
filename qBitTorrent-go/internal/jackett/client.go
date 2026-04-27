// Package jackett implements a thin HTTP client for the Jackett admin API
// covering session warmup, catalog browse, indexer template fetch,
// configuration POST, and indexer deletion. The client is stateless beyond
// the cookie jar carried in its underlying *http.Client.
package jackett

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"strings"
	"time"
)

// CatalogEntry is a single indexer entry returned by /api/v2.0/indexers.
type CatalogEntry struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Type        string `json:"type"`
	Configured  bool   `json:"configured"`
	Language    string `json:"language"`
	Description string `json:"description"`
}

// Client is the Jackett admin-API HTTP client.
type Client struct {
	base   string
	apiKey string
	http   *http.Client
}

// NewClient returns a Client targeting the given Jackett base URL and api key.
// cookiejar.New(nil) cannot fail with a nil options argument, so the discarded
// error is safe.
func NewClient(base, apiKey string) *Client {
	jar, _ := cookiejar.New(nil)
	return &Client{
		base:   strings.TrimRight(base, "/"),
		apiKey: apiKey,
		http:   &http.Client{Timeout: 30 * time.Second, Jar: jar},
	}
}

// WarmUp posts the dashboard form to obtain the Jackett session cookie that
// the catalog and config endpoints require. The default Jackett install
// accepts an empty admin password; if a non-empty admin password is set on
// the server, this call will silently no-op (status is not inspected because
// Jackett returns 302 on success and 200 on rejection without a clear marker).
func (c *Client) WarmUp() error {
	form := url.Values{"password": {""}}
	req, err := http.NewRequest("POST", c.base+"/UI/Dashboard", strings.NewReader(form.Encode()))
	if err != nil {
		return fmt.Errorf("build warmup request: %w", err)
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := c.http.Do(req)
	if err != nil {
		return fmt.Errorf("warmup: %w", err)
	}
	defer resp.Body.Close()
	return nil
}

// GetCatalog returns the unconfigured-indexer catalog used by the "Add
// indexer" UI. The configured=false query param scopes the result to
// indexers the user can still add (configured ones are filtered out).
func (c *Client) GetCatalog() ([]CatalogEntry, error) {
	u, err := url.Parse(c.base + "/api/v2.0/indexers")
	if err != nil {
		return nil, fmt.Errorf("parse catalog url: %w", err)
	}
	q := u.Query()
	q.Set("apikey", c.apiKey)
	q.Set("configured", "false")
	u.RawQuery = q.Encode()
	req, err := http.NewRequest("GET", u.String(), nil)
	if err != nil {
		return nil, fmt.Errorf("build catalog request: %w", err)
	}
	req.Header.Set("Accept", "application/json")
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("get catalog: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode == 401 {
		return nil, fmt.Errorf("jackett_auth_failed")
	}
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("jackett_catalog_http_%d", resp.StatusCode)
	}
	var entries []CatalogEntry
	if err := json.NewDecoder(resp.Body).Decode(&entries); err != nil {
		return nil, fmt.Errorf("decode: %w", err)
	}
	return entries, nil
}

// GetIndexerTemplate returns the configuration field template for the given
// indexer id. Jackett's response is either a top-level array of fields or a
// {config: [...]} envelope depending on version; both shapes are normalised
// to []map[string]any.
func (c *Client) GetIndexerTemplate(id string) ([]map[string]any, error) {
	u := fmt.Sprintf("%s/api/v2.0/indexers/%s/config?apikey=%s", c.base, id, c.apiKey)
	req, err := http.NewRequest("GET", u, nil)
	if err != nil {
		return nil, fmt.Errorf("build template request: %w", err)
	}
	req.Header.Set("Accept", "application/json")
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("get template: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("template fetch HTTP %d", resp.StatusCode)
	}
	var raw any
	if err := json.NewDecoder(resp.Body).Decode(&raw); err != nil {
		return nil, fmt.Errorf("decode template: %w", err)
	}
	switch v := raw.(type) {
	case []any:
		out := make([]map[string]any, 0, len(v))
		for _, item := range v {
			if m, ok := item.(map[string]any); ok {
				out = append(out, m)
			}
		}
		return out, nil
	case map[string]any:
		if cfg, ok := v["config"].([]any); ok {
			out := make([]map[string]any, 0, len(cfg))
			for _, item := range cfg {
				if m, ok := item.(map[string]any); ok {
					out = append(out, m)
				}
			}
			return out, nil
		}
	}
	return nil, fmt.Errorf("unexpected template shape")
}

// PostIndexerConfig submits filled-in template fields for the given indexer.
// The fields slice is JSON-encoded as the request body.
func (c *Client) PostIndexerConfig(id string, fields []map[string]any) error {
	u := fmt.Sprintf("%s/api/v2.0/indexers/%s/config?apikey=%s", c.base, id, c.apiKey)
	body, err := json.Marshal(fields)
	if err != nil {
		return fmt.Errorf("marshal config: %w", err)
	}
	req, err := http.NewRequest("POST", u, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("build config request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.http.Do(req)
	if err != nil {
		return fmt.Errorf("post config: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return fmt.Errorf("config POST HTTP %d", resp.StatusCode)
	}
	return nil
}

// DeleteIndexer removes a configured indexer. A 404 is treated as success
// (already absent) so the caller can drive idempotent reconciliation.
func (c *Client) DeleteIndexer(id string) error {
	u := fmt.Sprintf("%s/api/v2.0/indexers/%s?apikey=%s", c.base, id, c.apiKey)
	req, err := http.NewRequest("DELETE", u, nil)
	if err != nil {
		return fmt.Errorf("build delete request: %w", err)
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return fmt.Errorf("delete indexer: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 && resp.StatusCode != 404 {
		return fmt.Errorf("delete HTTP %d", resp.StatusCode)
	}
	return nil
}
