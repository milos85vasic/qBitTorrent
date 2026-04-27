package db

import (
	"crypto/rand"
	"testing"
)

func key32() []byte {
	k := make([]byte, 32)
	_, _ = rand.Read(k)
	return k
}

func TestEncryptDecryptRoundTrip(t *testing.T) {
	k := key32()
	plain := "rutracker_password_xyz!@#"
	blob, err := Encrypt(k, plain)
	if err != nil {
		t.Fatalf("Encrypt: %v", err)
	}
	got, err := Decrypt(k, blob)
	if err != nil {
		t.Fatalf("Decrypt: %v", err)
	}
	if got != plain {
		t.Fatalf("round-trip mismatch: got %q want %q", got, plain)
	}
}

func TestEncryptRejectsEmpty(t *testing.T) {
	if _, err := Encrypt(key32(), ""); err == nil {
		t.Fatal("expected error encrypting empty plaintext")
	}
}

func TestEncryptRejectsBadKey(t *testing.T) {
	if _, err := Encrypt(make([]byte, 16), "x"); err == nil {
		t.Fatal("expected error with 16-byte key")
	}
}

func TestDecryptDetectsTamper(t *testing.T) {
	k := key32()
	blob, _ := Encrypt(k, "secret")
	blob[len(blob)-1] ^= 0x01 // flip last bit
	if _, err := Decrypt(k, blob); err == nil {
		t.Fatal("expected GCM auth failure on tampered ciphertext")
	}
}

func TestNonceUniqueness(t *testing.T) {
	k := key32()
	seen := make(map[string]struct{}, 100000)
	for i := 0; i < 100000; i++ {
		blob, _ := Encrypt(k, "x")
		nonce := string(blob[:12])
		if _, dup := seen[nonce]; dup {
			t.Fatalf("nonce collision at iter %d", i)
		}
		seen[nonce] = struct{}{}
	}
}

func TestBlobShape(t *testing.T) {
	blob, _ := Encrypt(key32(), "x")
	if len(blob) < 12+16 { // nonce(12) + GCM tag(16) + at least 1 byte
		t.Fatalf("blob too short: %d", len(blob))
	}
}
