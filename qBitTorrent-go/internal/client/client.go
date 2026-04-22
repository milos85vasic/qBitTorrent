package client

import (
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"sync"
	"time"
)

type Client struct {
	BaseURL    *url.URL
	HTTPClient *http.Client
	mu         sync.RWMutex
	sid        string
}

func NewClient(baseURL, username, password string) (*Client, error) {
	u, err := url.Parse(baseURL)
	if err != nil {
		return nil, err
	}

	jar, _ := cookiejar.New(nil)
	c := &Client{
		BaseURL: u,
		HTTPClient: &http.Client{
			Jar:     jar,
			Timeout: 30 * time.Second,
		},
	}

	if err := c.Login(username, password); err != nil {
		return nil, err
	}
	return c, nil
}

func (c *Client) GetSID() string {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.sid
}