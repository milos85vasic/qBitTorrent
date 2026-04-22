package models

import "time"

type Hook struct {
	ID        string            `json:"id"`
	URL       string            `json:"url"`
	Secret   string            `json:"secret,omitempty"`
	Events   []string          `json:"events"`
	Headers  map[string]string `json:"headers,omitempty"`
	Enabled  bool              `json:"enabled"`
	CreatedAt time.Time       `json:"created_at,omitempty"`
}

type HookEventType string

const (
	HookEventSearchStart      HookEventType = "search_start"
	HookEventSearchComplete  HookEventType = "search_complete"
	HookEventDownloadStart   HookEventType = "download_start"
	HookEventDownloadComplete HookEventType = "download_complete"
)

type HookLogEntry struct {
	HookID    string    `json:"hook_id"`
	Event     string    `json:"event"`
	Timestamp time.Time `json:"timestamp"`
	Success   bool      `json:"success"`
	Error     string    `json:"error,omitempty"`
	Payload   string    `json:"payload,omitempty"`
}