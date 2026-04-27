package jackett

import (
	"sort"
	"strings"

	"github.com/agnivade/levenshtein"
)

// FuzzyThreshold is the minimum similarity score (in [0, 1]) a catalog entry
// must reach against an env name (or its lower-cased id/name form) to be
// considered a match candidate. Mirrors the Python autoconfig threshold.
const FuzzyThreshold = 0.85

// AmbiguousMatch records an env name that tied between multiple catalog
// candidates above FuzzyThreshold. The autoconfig run reports these for
// operator review (they require an explicit override to disambiguate).
//
// JSON tags exist so AutoconfigResult (and downstream API responses in
// Task 19) serialize this struct with stable, snake_case field names.
type AmbiguousMatch struct {
	EnvName    string   `json:"env_name"`
	Candidates []string `json:"candidates"`
}

// ratio returns a similarity score in [0, 1] using the classic edit-distance
// formula: 1 - LevenshteinDistance / max(len_a, len_b). This DIFFERS from the
// Python python-Levenshtein 0.21+ ratio() which uses an InDel-based formula
// (len_a + len_b - InDel) / (len_a + len_b). Both pin to 0 and 1 at the
// extremes; intermediate scores diverge. The Go formula is plan-locked for
// Task 12 — see docs/superpowers/plans/2026-04-27-jackett-management-ui-and-system-db.md.
func ratio(a, b string) float64 {
	if a == "" && b == "" {
		return 1.0
	}
	d := levenshtein.ComputeDistance(a, b)
	maxLen := len(a)
	if len(b) > maxLen {
		maxLen = len(b)
	}
	if maxLen == 0 {
		return 1.0
	}
	return 1.0 - float64(d)/float64(maxLen)
}

// MatchIndexers resolves env names (e.g. "RUTRACKER") to Jackett catalog ids
// using, in order: an explicit override map (only if the target id exists in
// the catalog), then a fuzzy match against catalog id and name with the
// higher of the two scores. Scores below FuzzyThreshold push the env name
// into unmatched; ties at the top score push it into ambiguous (with the
// tied ids in deterministic ascending order).
//
// Iteration order over envNames is preserved as the input slice order, so
// ambiguous and unmatched are deterministic for a given input. matched is a
// map and inherently unordered, but its contents per-key are deterministic.
func MatchIndexers(envNames []string, catalog []CatalogEntry, override map[string]string) (matched map[string]string, ambiguous []AmbiguousMatch, unmatched []string) {
	matched = map[string]string{}
	ids := map[string]bool{}
	for _, e := range catalog {
		ids[e.ID] = true
	}
	for _, name := range envNames {
		if t, ok := override[name]; ok && ids[t] {
			matched[name] = t
			continue
		}
		needle := strings.ToLower(name)
		type scored struct {
			id    string
			score float64
		}
		var scoredAll []scored
		for _, e := range catalog {
			s := ratio(needle, strings.ToLower(e.ID))
			if n := ratio(needle, strings.ToLower(e.Name)); n > s {
				s = n
			}
			if s >= FuzzyThreshold {
				scoredAll = append(scoredAll, scored{e.ID, s})
			}
		}
		if len(scoredAll) == 0 {
			unmatched = append(unmatched, name)
			continue
		}
		sort.Slice(scoredAll, func(i, j int) bool {
			if scoredAll[i].score != scoredAll[j].score {
				return scoredAll[i].score > scoredAll[j].score
			}
			return scoredAll[i].id < scoredAll[j].id
		})
		topScore := scoredAll[0].score
		var ties []string
		for _, s := range scoredAll {
			if s.score == topScore {
				ties = append(ties, s.id)
			}
		}
		if len(ties) == 1 {
			matched[name] = ties[0]
		} else {
			ambiguous = append(ambiguous, AmbiguousMatch{EnvName: name, Candidates: ties})
		}
	}
	return
}
