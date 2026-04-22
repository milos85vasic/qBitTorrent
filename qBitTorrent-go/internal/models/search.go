package models

type SearchRequest struct {
	Query              string `json:"query"`
	Category           string `json:"category"`
	Limit              int    `json:"limit,omitempty"`
	EnableMetadata     bool   `json:"enable_metadata,omitempty"`
	ValidateTrackers   bool   `json:"validate_trackers,omitempty"`
	SortBy             string `json:"sort_by,omitempty"`
	SortOrder          string `json:"sort_order,omitempty"`
}

type SearchResponse struct {
	SearchID         string          `json:"search_id"`
	Query            string          `json:"query"`
	Status           string          `json:"status"`
	Results          []TorrentResult `json:"results"`
	TotalResults     int             `json:"total_results"`
	MergedResults    int             `json:"merged_results"`
	TrackersSearched []string        `json:"trackers_searched"`
	Errors           []string        `json:"errors"`
	TrackerStats     []TrackerStat   `json:"tracker_stats"`
	StartedAt        string          `json:"started_at"`
	CompletedAt      *string         `json:"completed_at,omitempty"`
}

type TrackerStat struct {
	Name          string `json:"name"`
	Status       string `json:"status"`
	Results      int    `json:"results"`
	DurationMS   int64  `json:"duration_ms,omitempty"`
	Error        string `json:"error,omitempty"`
	Authenticated bool  `json:"authenticated,omitempty"`
}

type DownloadRequest struct {
	ResultID     string   `json:"result_id"`
	DownloadURLs []string `json:"download_urls"`
}

type DownloadResult struct {
	DownloadID string              `json:"download_id"`
	Status     string              `json:"status"`
	URLsCount  int                 `json:"urls_count"`
	AddedCount int                 `json:"added_count"`
	Results    []URLDownloadResult `json:"results"`
}

type URLDownloadResult struct {
	URL     string `json:"url"`
	Status  string `json:"status"`
	Detail  string `json:"detail,omitempty"`
	Method  string `json:"method,omitempty"`
	Message string `json:"message,omitempty"`
}