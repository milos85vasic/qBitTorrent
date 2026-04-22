package client

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestLogin_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/v2/auth/login" && r.Method == "POST" {
			http.SetCookie(w, &http.Cookie{Name: "SID", Value: "test-sid-123"})
			w.WriteHeader(http.StatusOK)
			w.Write([]byte("Ok."))
			return
		}
		w.WriteHeader(http.StatusNotFound)
	}))
	defer server.Close()

	client, err := NewClient(server.URL, "admin", "admin")
	require.NoError(t, err)
	assert.True(t, client.IsAuthenticated())
	assert.Equal(t, "test-sid-123", client.GetSID())
}

func TestLogin_Failure(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusForbidden)
		w.Write([]byte("Fails."))
	}))
	defer server.Close()

	_, err := NewClient(server.URL, "wrong", "wrong")
	assert.Error(t, err)
}

func TestClient_QueryString(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.SetCookie(w, &http.Cookie{Name: "SID", Value: "sid"})
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("Ok."))
	}))
	defer server.Close()

	client, err := NewClient(server.URL, "admin", "admin")
	require.NoError(t, err)
	assert.Equal(t, "http", client.BaseURL.Scheme)
}