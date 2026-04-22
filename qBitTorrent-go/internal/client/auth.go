package client

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
)

func (c *Client) Login(username, password string) error {
	loginURL := c.BaseURL.ResolveReference(&url.URL{Path: "/api/v2/auth/login"})
	data := url.Values{}
	data.Set("username", username)
	data.Set("password", password)

	resp, err := c.HTTPClient.PostForm(loginURL.String(), data)
	if err != nil {
		return fmt.Errorf("login request failed: %w", err)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("login failed: HTTP %d: %s", resp.StatusCode, string(body))
	}

	if strings.TrimSpace(string(body)) != "Ok." {
		return fmt.Errorf("login rejected: %s", strings.TrimSpace(string(body)))
	}

	for _, cookie := range c.HTTPClient.Jar.Cookies(loginURL) {
		if cookie.Name == "SID" {
			c.mu.Lock()
			c.sid = cookie.Value
			c.mu.Unlock()
			break
		}
	}
	return nil
}

func (c *Client) IsAuthenticated() bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.sid != ""
}