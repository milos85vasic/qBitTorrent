package models

import (
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestSearchRequest_JSON(t *testing.T) {
	raw := `{"query":"ubuntu","category":"all","limit":50,"enable_metadata":true}`
	var req SearchRequest
	err := json.Unmarshal([]byte(raw), &req)
	assert.NoError(t, err)
	assert.Equal(t, "ubuntu", req.Query)
	assert.Equal(t, "all", req.Category)
	assert.Equal(t, 50, req.Limit)
	assert.True(t, req.EnableMetadata)
}

func TestSearchResponse_JSON(t *testing.T) {
	now := "2026-01-01T00:00:00Z"
	resp := SearchResponse{
		SearchID:         "abc-123",
		Query:            "test",
		Status:           "completed",
		TotalResults:     5,
		MergedResults:    3,
		TrackersSearched: []string{"rutracker", "rutor"},
		StartedAt:        now,
	}
	data, err := json.Marshal(resp)
	assert.NoError(t, err)
	assert.Contains(t, string(data), `"search_id":"abc-123"`)
	assert.Contains(t, string(data), `"status":"completed"`)
}

func TestTorrentResult_JSON(t *testing.T) {
	tr := TorrentResult{
		Name:         "Ubuntu 24.04",
		Size:         "4.0 GB",
		Seeds:        100,
		Leechers:     50,
		DownloadURLs: []string{"http://example.com/file.torrent"},
		Tracker:      "rutracker",
		Quality:      "full_hd",
		ContentType:  "software",
		Freeleech:    true,
	}
	data, err := json.Marshal(tr)
	assert.NoError(t, err)
	assert.Contains(t, string(data), `"freeleech":true`)
	assert.Contains(t, string(data), `"seeds":100`)
}

func TestHook_JSON(t *testing.T) {
	h := Hook{
		ID:      "hook-1",
		URL:     "https://example.com/webhook",
		Events:  []string{"search_complete", "download_complete"},
		Headers: map[string]string{"Authorization": "Bearer token"},
		Enabled: true,
	}
	data, err := json.Marshal(h)
	assert.NoError(t, err)
	assert.Contains(t, string(data), `"enabled":true`)
}

func TestScheduledSearch_JSON(t *testing.T) {
	s := ScheduledSearch{
		ID:       "sched-1",
		Query:    "ubuntu",
		Category: "software",
		Cron:     "0 */6 * * *",
		Enabled:  true,
	}
	data, err := json.Marshal(s)
	assert.NoError(t, err)
	assert.Contains(t, string(data), `"cron":"0 */6 * * *"`)
}

func TestThemeState_JSON(t *testing.T) {
	ts := ThemeState{
		PaletteID: "dark-midnight",
		Mode:      "dark",
	}
	data, err := json.Marshal(ts)
	assert.NoError(t, err)
	assert.Contains(t, string(data), `"palette_id":"dark-midnight"`)
	assert.Contains(t, string(data), `"mode":"dark"`)
}

func TestTrackerStat_JSON(t *testing.T) {
	ts := TrackerStat{
		Name:    "rutracker",
		Status:  "success",
		Results: 42,
	}
	data, err := json.Marshal(ts)
	assert.NoError(t, err)
	assert.Contains(t, string(data), `"results":42`)
}

func TestDownloadRequest_JSON(t *testing.T) {
	raw := `{"result_id":"r-1","download_urls":["http://example.com/file.torrent"]}`
	var req DownloadRequest
	err := json.Unmarshal([]byte(raw), &req)
	assert.NoError(t, err)
	assert.Equal(t, "r-1", req.ResultID)
	assert.Len(t, req.DownloadURLs, 1)
}