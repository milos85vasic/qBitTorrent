package db

import (
	"crypto/rand"
	"testing"
)

// BenchmarkEncryptDecrypt covers spec §10.5: encrypt+decrypt a
// representative credential string. Target p99 < 1ms (a credential
// upsert path runs one Encrypt + one Decrypt per Get round-trip — the
// dashboard does many of these per page render).
//
// Run:
//
//	GOMAXPROCS=2 nice -n 19 ionice -c 3 go test -bench=. -benchmem \
//	  -benchtime=3s ./internal/db/ -run=^$
func BenchmarkEncryptDecrypt(b *testing.B) {
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		b.Fatalf("rand: %v", err)
	}
	plaintext := "p4ssw0rd-with-typical-tracker-cookie-length-cf_clearance=01234567"

	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		blob, err := Encrypt(key, plaintext)
		if err != nil {
			b.Fatalf("Encrypt: %v", err)
		}
		got, err := Decrypt(key, blob)
		if err != nil {
			b.Fatalf("Decrypt: %v", err)
		}
		if got != plaintext {
			b.Fatalf("round-trip mismatch")
		}
	}
}
