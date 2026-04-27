// Package logging provides a writer-level secret redactor that wraps
// any io.Writer and replaces pre-registered plaintext secrets with a
// fixed mask before they reach the underlying sink.
//
// Intended use: install as the global zerolog (or stdlib log) writer in
// main.go AFTER the bootstrap path has decrypted credentials via
// repos/credentials.Repo.List + Get, then call AddSecret for every
// plaintext value that must never appear in logs (tracker passwords,
// API keys, NNMClub cookies, etc.). RemoveSecret reverses a registration
// when a credential is rotated or deleted.
//
// This package deliberately avoids any logging-library dependency
// (no zerolog/zap) — the redactor is just an io.Writer, so it composes
// with whatever logger main.go chooses.
package logging

import (
	"bytes"
	"io"
	"sync"
)

// Redactor is an io.Writer that replaces every occurrence of each
// registered secret in its input with the mask string before forwarding
// to the wrapped destination writer. Safe for concurrent use.
//
// Note on secret-ordering: bytes.ReplaceAll runs in registration order,
// so callers should AddSecret LONGER secrets BEFORE shorter ones that
// might be substrings of them. Otherwise the shorter secret will be
// masked first and leave fragments of the longer secret unmasked.
//
// CONST-013 note: `secrets` is a mutable slice guarded by a bare
// sync.RWMutex. Per project rule 13, mutable collections SHOULD use
// safe.Slice[T] from digital.vasic.concurrency/pkg/safe. That module
// is not currently in this go.mod's import graph (verified 2026-04-27);
// when it lands, refactor `secrets` to safe.Slice[[]byte]. The current
// implementation is correct (-race clean) but does not satisfy the
// preferred primitive contract.
type Redactor struct {
	dest    io.Writer
	mu      sync.RWMutex
	secrets [][]byte
	mask    []byte
}

// NewRedactor returns a Redactor that forwards (post-redaction) writes
// to dest. The mask is a fixed three-asterisk marker.
func NewRedactor(dest io.Writer) *Redactor {
	return &Redactor{dest: dest, mask: []byte("***")}
}

// AddSecret registers s for redaction. Empty strings are ignored to
// avoid poisoning the secret list (an empty needle would cause
// bytes.ReplaceAll to insert the mask between every byte of input).
func (r *Redactor) AddSecret(s string) {
	if s == "" {
		return
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.secrets = append(r.secrets, []byte(s))
}

// RemoveSecret unregisters the first matching secret, if present.
// No-op for empty strings or unknown values.
func (r *Redactor) RemoveSecret(s string) {
	if s == "" {
		return
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	target := []byte(s)
	for i, sec := range r.secrets {
		if bytes.Equal(sec, target) {
			r.secrets = append(r.secrets[:i], r.secrets[i+1:]...)
			return
		}
	}
}

// Write applies every registered secret replacement to p, then forwards
// the redacted bytes to the destination writer.
//
// Return-value contract: Write always returns len(p) (modulo error). The
// caller's input slice is fully "consumed" by the redactor regardless of
// whether the underlying dest.Write succeeds, because the transformation
// happens entirely in memory before the forward — there is no partial-
// consume scenario from the caller's perspective. Returning len(p) keeps
// the io.Writer contract `0 <= n <= len(p)` and prevents log libraries
// from re-writing the same bytes on a transient downstream error.
//
// Locking: holds the RLock for the duration of dest.Write. If dest is a
// slow sink, concurrent writers will queue. For os.Stderr/os.Stdout this
// is fine; for network sinks, wrap dest in a buffered writer.
func (r *Redactor) Write(p []byte) (int, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	out := p
	for _, sec := range r.secrets {
		out = bytes.ReplaceAll(out, sec, r.mask)
	}
	_, err := r.dest.Write(out)
	return len(p), err
}
