package db

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"errors"
	"fmt"
	"io"
)

const (
	nonceSize = 12
	keySize   = 32 // AES-256
)

var (
	ErrEmptyPlaintext = errors.New("crypto: empty plaintext")
	ErrShortBlob      = errors.New("crypto: blob shorter than nonce")
	ErrBadKeySize     = errors.New("crypto: key must be 32 bytes (AES-256)")
)

func Encrypt(key []byte, plaintext string) ([]byte, error) {
	if len(key) != keySize {
		return nil, ErrBadKeySize
	}
	if len(plaintext) == 0 {
		return nil, ErrEmptyPlaintext
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, fmt.Errorf("aes.NewCipher: %w", err)
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, fmt.Errorf("cipher.NewGCM: %w", err)
	}
	nonce := make([]byte, nonceSize)
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, fmt.Errorf("rand.Read: %w", err)
	}
	ct := gcm.Seal(nil, nonce, []byte(plaintext), nil)
	out := make([]byte, 0, nonceSize+len(ct))
	out = append(out, nonce...)
	out = append(out, ct...)
	return out, nil
}

func Decrypt(key []byte, blob []byte) (string, error) {
	if len(key) != keySize {
		return "", ErrBadKeySize
	}
	if len(blob) < nonceSize {
		return "", ErrShortBlob
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return "", fmt.Errorf("aes.NewCipher: %w", err)
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("cipher.NewGCM: %w", err)
	}
	nonce, ct := blob[:nonceSize], blob[nonceSize:]
	pt, err := gcm.Open(nil, nonce, ct, nil)
	if err != nil {
		return "", fmt.Errorf("gcm.Open: %w", err)
	}
	return string(pt), nil
}
