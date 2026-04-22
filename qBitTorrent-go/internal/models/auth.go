package models

type AuthStatus struct {
	Authenticated  bool   `json:"authenticated"`
	CaptchaRequired bool `json:"captcha_required,omitempty"`
	CaptchaURL     string `json:"captcha_url,omitempty"`
}

type TrackerLoginRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

type CookieLoginRequest struct {
	Cookies string `json:"cookies"`
}

type QBittorrentAuthRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
	Save     bool   `json:"save"`
}

type QBittorrentAuthResponse struct {
	Status  string `json:"status"`
	Version string `json:"version,omitempty"`
	Message string `json:"message,omitempty"`
	Error   string `json:"error,omitempty"`
}