package jackett

import "testing"

// TestFuzzyMatchExactNameReturnsIndexer mirrors the Python
// test_fuzzy_match_exact_name_returns_indexer test: a RUTRACKER bundle against
// a catalog containing an exact-name RuTracker entry resolves cleanly with no
// override, no ambiguous, and no unmatched.
func TestFuzzyMatchExactNameReturnsIndexer(t *testing.T) {
	catalog := []CatalogEntry{
		{ID: "rutracker", Name: "RuTracker"},
		{ID: "kinozalbiz", Name: "KinoZal"},
	}
	matched, ambiguous, unmatched := MatchIndexers([]string{"RUTRACKER"}, catalog, map[string]string{})
	if len(matched) != 1 || matched["RUTRACKER"] != "rutracker" {
		t.Fatalf("matched: %+v", matched)
	}
	if len(ambiguous) != 0 {
		t.Fatalf("ambiguous: %+v", ambiguous)
	}
	if len(unmatched) != 0 {
		t.Fatalf("unmatched: %+v", unmatched)
	}
}

// TestFuzzyMatchBelowThresholdGoesToUnmatched mirrors the Python
// test_fuzzy_match_below_threshold_goes_to_unmatched: when no catalog entry
// crosses the FuzzyThreshold the env name lands in unmatched.
func TestFuzzyMatchBelowThresholdGoesToUnmatched(t *testing.T) {
	catalog := []CatalogEntry{{ID: "demonoid", Name: "Demonoid"}}
	matched, _, unmatched := MatchIndexers([]string{"RUTRACKER"}, catalog, map[string]string{})
	if len(matched) != 0 {
		t.Fatalf("matched: %+v", matched)
	}
	if len(unmatched) != 1 || unmatched[0] != "RUTRACKER" {
		t.Fatalf("unmatched: %+v", unmatched)
	}
}

// TestFuzzyMatchAmbiguousRecordsCandidates mirrors the Python
// test_fuzzy_match_ambiguous_records_candidates: two catalog entries that are
// equally close to "NNMCLUB" must EITHER produce a deterministic top-pick in
// matched, OR record the env name in ambiguous. Both outcomes are accepted.
func TestFuzzyMatchAmbiguousRecordsCandidates(t *testing.T) {
	catalog := []CatalogEntry{
		{ID: "nnmclub", Name: "NNMClub"},
		{ID: "nnmclub2", Name: "NNMClub2"},
	}
	matched, ambiguous, _ := MatchIndexers([]string{"NNMCLUB"}, catalog, map[string]string{})
	if _, ok := matched["NNMCLUB"]; ok {
		// matched OK
	} else {
		found := false
		for _, a := range ambiguous {
			if a.EnvName == "NNMCLUB" {
				found = true
				break
			}
		}
		if !found {
			t.Fatalf("expected NNMCLUB in matched or ambiguous: matched=%+v ambiguous=%+v", matched, ambiguous)
		}
	}
}

// TestOverrideTakesPrecedenceOverFuzzyMatch mirrors the Python
// test_override_takes_precedence_over_fuzzy_match: a valid override id beats
// the fuzzy winner.
func TestOverrideTakesPrecedenceOverFuzzyMatch(t *testing.T) {
	catalog := []CatalogEntry{
		{ID: "rutracker", Name: "RuTracker"},
		{ID: "rutrackerme", Name: "RutrackerMe"},
	}
	matched, _, _ := MatchIndexers([]string{"RUTRACKER"}, catalog, map[string]string{"RUTRACKER": "rutrackerme"})
	if len(matched) != 1 || matched["RUTRACKER"] != "rutrackerme" {
		t.Fatalf("matched: %+v", matched)
	}
}

// TestOverrideToUnknownIdFallsBackToFuzzy mirrors the Python
// test_override_to_unknown_id_falls_back_to_fuzzy: when the override target id
// is absent from the catalog, the matcher falls through to the fuzzy result.
func TestOverrideToUnknownIdFallsBackToFuzzy(t *testing.T) {
	catalog := []CatalogEntry{{ID: "rutracker", Name: "RuTracker"}}
	matched, _, _ := MatchIndexers([]string{"RUTRACKER"}, catalog, map[string]string{"RUTRACKER": "does-not-exist"})
	if len(matched) != 1 || matched["RUTRACKER"] != "rutracker" {
		t.Fatalf("matched: %+v", matched)
	}
}
