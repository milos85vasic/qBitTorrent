package envfile

import (
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
)

func TestWriteRoundTrip(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, ".env")
	if err := os.WriteFile(p, []byte("FOO=bar\n"), 0600); err != nil {
		t.Fatalf("seed: %v", err)
	}
	if err := Upsert(p, map[string]string{"BAZ": "qux", "FOO": "baz"}); err != nil {
		t.Fatalf("Upsert: %v", err)
	}
	body, _ := os.ReadFile(p)
	s := string(body)
	if !strings.Contains(s, "BAZ=qux") {
		t.Fatalf("missing BAZ=qux:\n%s", s)
	}
	if !strings.Contains(s, "FOO=baz") {
		t.Fatalf("missing FOO=baz:\n%s", s)
	}
	if strings.Contains(s, "FOO=bar") {
		t.Fatalf("old FOO=bar still present:\n%s", s)
	}
}

func TestWriteMode0600(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, ".env")
	os.WriteFile(p, []byte("FOO=bar\n"), 0644)
	_ = Upsert(p, map[string]string{"FOO": "baz"})
	st, _ := os.Stat(p)
	if st.Mode().Perm() != 0600 {
		t.Fatalf("want mode 0600, got %v", st.Mode().Perm())
	}
}

func TestDeleteKey(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, ".env")
	os.WriteFile(p, []byte("FOO=bar\nBAZ=qux\n"), 0600)
	if err := Delete(p, []string{"FOO"}); err != nil {
		t.Fatalf("Delete: %v", err)
	}
	body, _ := os.ReadFile(p)
	if strings.Contains(string(body), "FOO=") {
		t.Fatalf("FOO not deleted:\n%s", body)
	}
	if !strings.Contains(string(body), "BAZ=qux") {
		t.Fatalf("BAZ removed unexpectedly:\n%s", body)
	}
}

func TestConcurrentWritesNoCorruption(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, ".env")
	os.WriteFile(p, []byte(""), 0600)
	var wg sync.WaitGroup
	for n := 0; n < 50; n++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_ = Upsert(p, map[string]string{"K": "v"})
			_ = Upsert(p, map[string]string{"K2": "v2"})
		}()
	}
	wg.Wait()
	body, _ := os.ReadFile(p)
	got, err := Parse(strings.NewReader(string(body)))
	if err != nil {
		t.Fatalf("post-concurrent parse: %v\nbody:\n%s", err, body)
	}
	if got["K"] != "v" || got["K2"] != "v2" {
		t.Fatalf("post-concurrent values lost: %+v", got)
	}
}

func TestDeleteOnMissingFileNoCreate(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, ".env")
	if err := Delete(p, []string{"FOO"}); err != nil {
		t.Fatalf("Delete: %v", err)
	}
	if _, err := os.Stat(p); !os.IsNotExist(err) {
		t.Fatalf("Delete created a file at %s when it should not have", p)
	}
}

func TestCRLFNormalizedOnRead(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, ".env")
	// Seed with Windows line endings.
	os.WriteFile(p, []byte("FOO=bar\r\nBAZ=qux\r\n"), 0600)
	if err := Upsert(p, map[string]string{"NEW": "v"}); err != nil {
		t.Fatalf("Upsert: %v", err)
	}
	body, _ := os.ReadFile(p)
	if strings.Contains(string(body), "\r") {
		t.Fatalf("CR remained after upsert:\n%q", body)
	}
	got, _ := Parse(strings.NewReader(string(body)))
	if got["FOO"] != "bar" || got["BAZ"] != "qux" || got["NEW"] != "v" {
		t.Fatalf("values lost or mangled: %+v", got)
	}
}
