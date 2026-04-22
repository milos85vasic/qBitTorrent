package models

type TorrentResult struct {
	Name         string                  `json:"name"`
	Size         interface{}             `json:"size"`
	Seeds        int                    `json:"seeds"`
	Leechers     int                    `json:"leechers"`
	DownloadURLs []string               `json:"download_urls"`
	Quality      string                 `json:"quality,omitempty"`
	ContentType  string                 `json:"content_type,omitempty"`
	DescLink     string                 `json:"desc_link,omitempty"`
	Tracker      string                 `json:"tracker,omitempty"`
	Sources      []SourceInfo           `json:"sources,omitempty"`
	Metadata     map[string]interface{} `json:"metadata,omitempty"`
	Freeleech    bool                   `json:"freeleech"`
}

type SourceInfo struct {
	Tracker  string `json:"tracker"`
	Seeds    int    `json:"seeds"`
	Leechers int    `json:"leechers"`
}