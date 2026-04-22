package client

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
)

type QBSearchResult struct {
	FileName   string `json:"fileName"`
	FileSize   int64  `json:"fileSize"`
	NbSeeders  int    `json:"nbSeeders"`
	NbLeechers int    `json:"nbLeechers"`
	SiteURL    string `json:"siteUrl"`
	FileURL    string `json:"fileUrl"`
	DescrLink  string `json:"descrLink"`
}

type QBSearchResponse struct {
	Results []QBSearchResult `json:"results"`
	Total   int            `json:"total"`
	Status  string         `json:"status"`
}

func (c *Client) StartSearch(query string, plugins []string, category string) (int, error) {
	searchURL := c.BaseURL.ResolveReference(&url.URL{Path: "/api/v2/search/start"})
	data := url.Values{}
	data.Set("pattern", query)
	data.Set("category", category)
	for _, p := range plugins {
		data.Add("plugins", p)
	}

	resp, err := c.HTTPClient.PostForm(searchURL.String(), data)
	if err != nil {
		return 0, fmt.Errorf("search start request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("search start failed: HTTP %d", resp.StatusCode)
	}

	var result struct {
		ID int `json:"id"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return 0, fmt.Errorf("failed to decode search response: %w", err)
	}
	return result.ID, nil
}

func (c *Client) GetSearchResults(searchID int, limit, offset int) ([]QBSearchResult, int, error) {
	resultsURL := c.BaseURL.ResolveReference(&url.URL{Path: "/api/v2/search/results"})
	q := resultsURL.Query()
	q.Set("id", strconv.Itoa(searchID))
	if limit > 0 {
		q.Set("limit", strconv.Itoa(limit))
	}
	if offset > 0 {
		q.Set("offset", strconv.Itoa(offset))
	}
	resultsURL.RawQuery = q.Encode()

	resp, err := c.HTTPClient.Get(resultsURL.String())
	if err != nil {
		return nil, 0, fmt.Errorf("get search results request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, 0, fmt.Errorf("failed to get results: HTTP %d", resp.StatusCode)
	}

	var response QBSearchResponse
	if err := json.NewDecoder(resp.Body).Decode(&response); err != nil {
		return nil, 0, fmt.Errorf("failed to decode results: %w", err)
	}
	return response.Results, response.Total, nil
}

func (c *Client) StopSearch(searchID int) error {
	stopURL := c.BaseURL.ResolveReference(&url.URL{Path: "/api/v2/search/stop"})
	data := url.Values{}
	data.Set("id", strconv.Itoa(searchID))

	resp, err := c.HTTPClient.PostForm(stopURL.String(), data)
	if err != nil {
		return fmt.Errorf("stop search request failed: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("failed to stop search: HTTP %d", resp.StatusCode)
	}
	return nil
}

func (c *Client) SearchStatus(searchID int) (string, error) {
	statusURL := c.BaseURL.ResolveReference(&url.URL{Path: "/api/v2/search/status"})
	q := statusURL.Query()
	q.Set("id", strconv.Itoa(searchID))
	statusURL.RawQuery = q.Encode()

	resp, err := c.HTTPClient.Get(statusURL.String())
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var result struct {
		Status string `json:"status"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", err
	}
	return result.Status, nil
}

func (c *Client) ListPlugins() ([]map[string]interface{}, error) {
	pluginsURL := c.BaseURL.ResolveReference(&url.URL{Path: "/api/v2/search/plugins"})
	resp, err := c.HTTPClient.Get(pluginsURL.String())
	if err != nil {
		return nil, fmt.Errorf("list plugins request failed: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("failed to list plugins: HTTP %d", resp.StatusCode)
	}
	var plugins []map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&plugins); err != nil {
		return nil, fmt.Errorf("failed to decode plugins: %w", err)
	}
	return plugins, nil
}