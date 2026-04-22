package client

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/url"
)

func (c *Client) GetTorrents() ([]map[string]interface{}, error) {
	infoURL := c.BaseURL.ResolveReference(&url.URL{Path: "/api/v2/torrents/info"})
	resp, err := c.HTTPClient.Get(infoURL.String())
	if err != nil {
		return nil, fmt.Errorf("get torrents request failed: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("failed to get torrents: HTTP %d", resp.StatusCode)
	}
	var torrents []map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&torrents); err != nil {
		return nil, fmt.Errorf("failed to decode torrents: %w", err)
	}
	return torrents, nil
}

func (c *Client) AddTorrent(torrentURL, savepath, category string) error {
	addURL := c.BaseURL.ResolveReference(&url.URL{Path: "/api/v2/torrents/add"})
	data := url.Values{}
	data.Set("urls", torrentURL)
	if savepath != "" {
		data.Set("savepath", savepath)
	}
	if category != "" {
		data.Set("category", category)
	}

	resp, err := c.HTTPClient.PostForm(addURL.String(), data)
	if err != nil {
		return fmt.Errorf("add torrent request failed: %w", err)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK || string(body) == "Fails." {
		return fmt.Errorf("add torrent failed: HTTP %d: %s", resp.StatusCode, string(body))
	}
	return nil
}

func (c *Client) AddTorrentFile(filename string, fileData []byte) error {
	addURL := c.BaseURL.ResolveReference(&url.URL{Path: "/api/v2/torrents/add"})

	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)
	part, err := writer.CreateFormFile("torrents", filename)
	if err != nil {
		return fmt.Errorf("create form file failed: %w", err)
	}
	if _, err := part.Write(fileData); err != nil {
		return fmt.Errorf("write torrent data failed: %w", err)
	}
	writer.Close()

	req, err := http.NewRequest("POST", addURL.String(), &buf)
	if err != nil {
		return fmt.Errorf("create request failed: %w", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return fmt.Errorf("upload torrent request failed: %w", err)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK || string(body) == "Fails." {
		return fmt.Errorf("upload torrent failed: HTTP %d: %s", resp.StatusCode, string(body))
	}
	return nil
}

func (c *Client) GetAppVersion() (string, error) {
	versionURL := c.BaseURL.ResolveReference(&url.URL{Path: "/api/v2/app/version"})
	resp, err := c.HTTPClient.Get(versionURL.String())
	if err != nil {
		return "unknown", err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return "unknown", nil
	}
	return string(body), nil
}