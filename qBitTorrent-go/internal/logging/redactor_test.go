package logging

import (
	"bytes"
	"strings"
	"testing"
)

func TestRedactorReplacesSecrets(t *testing.T) {
	var buf bytes.Buffer
	r := NewRedactor(&buf)
	r.AddSecret("supersecret123")
	r.Write([]byte("user logged in with password=supersecret123 ok"))
	if strings.Contains(buf.String(), "supersecret123") {
		t.Fatalf("secret leaked: %s", buf.String())
	}
	if !strings.Contains(buf.String(), "***") {
		t.Fatalf("no redaction marker: %s", buf.String())
	}
}

func TestRedactorMultipleSecrets(t *testing.T) {
	var buf bytes.Buffer
	r := NewRedactor(&buf)
	r.AddSecret("aaa")
	r.AddSecret("bbb")
	r.Write([]byte("aaa bbb ccc"))
	if strings.Contains(buf.String(), "aaa") || strings.Contains(buf.String(), "bbb") {
		t.Fatalf("secret leaked: %s", buf.String())
	}
}
