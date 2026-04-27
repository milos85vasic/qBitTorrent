package jackett

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestSessionWarmupAndCatalog(t *testing.T) {
	warmedUp := false
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == "POST" && r.URL.Path == "/UI/Dashboard":
			http.SetCookie(w, &http.Cookie{Name: "Jackett", Value: "session"})
			warmedUp = true
			w.WriteHeader(302)
		case r.URL.Path == "/api/v2.0/indexers":
			if !warmedUp {
				w.WriteHeader(401)
				return
			}
			w.Header().Set("Content-Type", "application/json")
			w.Write([]byte(`[{"id":"rutracker","name":"RuTracker.org","type":"private","configured":false}]`))
		}
	}))
	defer srv.Close()
	c := NewClient(srv.URL, "test-key")
	if err := c.WarmUp(); err != nil {
		t.Fatalf("WarmUp: %v", err)
	}
	cat, err := c.GetCatalog()
	if err != nil {
		t.Fatalf("GetCatalog: %v", err)
	}
	if len(cat) != 1 || cat[0].ID != "rutracker" {
		t.Fatalf("got %+v", cat)
	}
}

func TestPostConfig(t *testing.T) {
	var captured string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "POST" && strings.Contains(r.URL.Path, "/config") {
			body := make([]byte, 1024)
			n, _ := r.Body.Read(body)
			captured = string(body[:n])
			w.WriteHeader(200)
		}
	}))
	defer srv.Close()
	c := NewClient(srv.URL, "k")
	body := []map[string]any{{"id": "username", "value": "u"}}
	if err := c.PostIndexerConfig("x", body); err != nil {
		t.Fatalf("Post: %v", err)
	}
	if !strings.Contains(captured, `"username"`) {
		t.Fatalf("body not posted: %s", captured)
	}
}
