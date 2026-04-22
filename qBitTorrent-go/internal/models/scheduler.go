package models

type ScheduledSearch struct {
	ID       string `json:"id"`
	Query    string `json:"query"`
	Category string `json:"category"`
	Cron     string `json:"cron"`
	Enabled  bool   `json:"enabled"`
}

type ScheduleStatus struct {
	Searches []ScheduledSearch `json:"searches"`
	Running  bool             `json:"running"`
}