package client

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestStartSearch(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/v2/auth/login" {
			http.SetCookie(w, &http.Cookie{Name: "SID", Value: "sid"})
			w.WriteHeader(http.StatusOK)
			w.Write([]byte("Ok."))
			return
		}
		if r.URL.Path == "/api/v2/search/start" {
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]int{"id": 42})
			return
		}
	}))
	defer server.Close()

	client, err := NewClient(server.URL, "admin", "admin")
	require.NoError(t, err)

	id, err := client.StartSearch("ubuntu", []string{"all"}, "all")
	assert.NoError(t, err)
	assert.Equal(t, 42, id)
}

func TestGetSearchResults(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/v2/auth/login" {
			http.SetCookie(w, &http.Cookie{Name: "SID", Value: "sid"})
			w.WriteHeader(http.StatusOK)
			w.Write([]byte("Ok."))
			return
		}
		if r.URL.Path == "/api/v2/search/results" {
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]interface{}{
				"results": []map[string]interface{}{
					{"fileName": "ubuntu.iso", "fileSize": int64(4000000000), "nbSeeders": 100, "nbLeechers": 50},
				},
				"total":  1,
				"status": "Stopped",
			})
			return
		}
	}))
	defer server.Close()

	client, err := NewClient(server.URL, "admin", "admin")
	require.NoError(t, err)

	results, total, err := client.GetSearchResults(1, 100, 0)
	assert.NoError(t, err)
	assert.Equal(t, 1, total)
	assert.Len(t, results, 1)
}

func TestStopSearch(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/v2/auth/login" {
			http.SetCookie(w, &http.Cookie{Name: "SID", Value: "sid"})
			w.WriteHeader(http.StatusOK)
			w.Write([]byte("Ok."))
			return
		}
		if r.URL.Path == "/api/v2/search/stop" {
			w.WriteHeader(http.StatusOK)
			return
		}
	}))
	defer server.Close()

	client, err := NewClient(server.URL, "admin", "admin")
	require.NoError(t, err)

	err = client.StopSearch(42)
	assert.NoError(t, err)
}

func TestAddTorrent(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/v2/auth/login" {
			http.SetCookie(w, &http.Cookie{Name: "SID", Value: "sid"})
			w.WriteHeader(http.StatusOK)
			w.Write([]byte("Ok."))
			return
		}
		if r.URL.Path == "/api/v2/torrents/add" {
			w.WriteHeader(http.StatusOK)
			w.Write([]byte("Ok."))
			return
		}
	}))
	defer server.Close()

	client, err := NewClient(server.URL, "admin", "admin")
	require.NoError(t, err)

	err = client.AddTorrent("http://example.com/file.torrent", "", "")
	assert.NoError(t, err)
}