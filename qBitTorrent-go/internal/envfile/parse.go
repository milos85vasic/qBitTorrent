// Package envfile parses and atomically rewrites simple shell-style
// .env files (KEY=VALUE lines, with comments and blanks).
//
// This is intentionally a minimal parser — it does NOT support shell
// variable expansion ($VAR), command substitution, multiline values,
// or escape sequences. .env files in this project are configuration,
// not scripts.
package envfile

import (
	"bufio"
	"io"
	"strings"
)

// Parse reads .env-style content and returns the resulting key/value map.
// Behavior:
//   - Lines beginning with `#` (after leading whitespace) are comments.
//   - Blank lines are ignored.
//   - The first `=` on a line splits key and value; subsequent `=` are
//     part of the value verbatim.
//   - Whitespace around the key is trimmed; whitespace around the value
//     is trimmed BEFORE any quote processing.
//   - If the trimmed value begins and ends with matching `"` or `'`,
//     the surrounding quotes are stripped (no escape processing inside).
//   - For duplicate keys, the LAST occurrence wins (matches shell behavior).
//   - Each line must fit within bufio.Scanner's default 64KB token limit; longer lines cause a scanner error.
func Parse(r io.Reader) (map[string]string, error) {
	out := map[string]string{}
	sc := bufio.NewScanner(r)
	for sc.Scan() {
		line := sc.Text()
		t := strings.TrimSpace(line)
		if t == "" || strings.HasPrefix(t, "#") {
			continue
		}
		eq := strings.IndexByte(t, '=')
		if eq < 0 {
			continue
		}
		k := strings.TrimSpace(t[:eq])
		if k == "" {
			continue
		}
		v := strings.TrimSpace(t[eq+1:])
		// strip matching surrounding quotes
		if len(v) >= 2 {
			if (v[0] == '"' && v[len(v)-1] == '"') || (v[0] == '\'' && v[len(v)-1] == '\'') {
				v = v[1 : len(v)-1]
			}
		}
		out[k] = v
	}
	if err := sc.Err(); err != nil {
		return nil, err
	}
	return out, nil
}
