package bootstrap

import "regexp"

// credRE matches legacy credential triple keys: NAME_USERNAME,
// NAME_PASSWORD, NAME_COOKIES. NAME captures group 1, the kind
// captures group 2. The non-greedy NAME quantifier ensures the LAST
// _USERNAME/_PASSWORD/_COOKIES suffix splits the key.
var credRE = regexp.MustCompile(`^([A-Z][A-Z0-9_]+?)_(USERNAME|PASSWORD|COOKIES)$`)

// CredBundle is a discovered credential triple — at least one of
// (Username + Password) or Cookies is non-empty.
type CredBundle struct {
	Name     string
	Username string
	Password string
	Cookies  string
}

// DiscoverCredentialBundles scans an .env-derived map for credential
// triples (NAME_USERNAME, NAME_PASSWORD, NAME_COOKIES) and returns one
// bundle per NAME that has either a complete username+password pair OR
// a non-empty cookies value. Names whose prefix matches the exclude
// set are skipped. Order of returned bundles is non-deterministic
// (map iteration); callers that need ordering should sort.
func DiscoverCredentialBundles(env map[string]string, exclude map[string]bool) []*CredBundle {
	groups := map[string]*CredBundle{}
	for k, v := range env {
		m := credRE.FindStringSubmatch(k)
		if m == nil {
			continue
		}
		name, kind := m[1], m[2]
		if exclude[name] {
			continue
		}
		b := groups[name]
		if b == nil {
			b = &CredBundle{Name: name}
			groups[name] = b
		}
		switch kind {
		case "USERNAME":
			b.Username = v
		case "PASSWORD":
			b.Password = v
		case "COOKIES":
			b.Cookies = v
		}
	}
	var out []*CredBundle
	for _, b := range groups {
		hasUP := b.Username != "" && b.Password != ""
		hasC := b.Cookies != ""
		if hasUP || hasC {
			out = append(out, b)
		}
	}
	return out
}
