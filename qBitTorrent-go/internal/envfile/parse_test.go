package envfile

import (
	"reflect"
	"strings"
	"testing"
)

func TestParseAllForms(t *testing.T) {
	src := `# header comment
FOO=bar
QUOTED="hello world"
SINGLE='hi'
EMPTY=
SPACED  =  trimmed
# another comment
DUP=first
DUP=second
`
	got, err := Parse(strings.NewReader(src))
	if err != nil {
		t.Fatalf("Parse: %v", err)
	}
	want := map[string]string{
		"FOO": "bar", "QUOTED": "hello world", "SINGLE": "hi",
		"EMPTY": "", "SPACED": "trimmed", "DUP": "second",
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %+v want %+v", got, want)
	}
}

func TestParseHandlesBlanks(t *testing.T) {
	src := "\n\n\nFOO=bar\n\n"
	got, _ := Parse(strings.NewReader(src))
	if got["FOO"] != "bar" {
		t.Fatalf("got %+v", got)
	}
}

func TestParseEdgeCases(t *testing.T) {
	cases := []struct {
		name string
		in   string
		want map[string]string
	}{
		{"value with equals", "KEY=a=b\n", map[string]string{"KEY": "a=b"}},
		{"hash inside value", "KEY=foo#bar\n", map[string]string{"KEY": "foo#bar"}},
		{"empty quoted string", `KEY=""` + "\n", map[string]string{"KEY": ""}},
		{"empty single-quoted", `KEY=''` + "\n", map[string]string{"KEY": ""}},
		{"mismatched quotes preserved", `KEY="hello'` + "\n", map[string]string{"KEY": `"hello'`}},
		{"single-char value", `KEY="` + "\n", map[string]string{"KEY": `"`}},
		{"only equals line skipped", "=value\n", map[string]string{}},
		{"whitespace-only key skipped", "   =value\n", map[string]string{}},
		{"line without equals skipped", "JUST_A_KEY\n", map[string]string{}},
		{"value with internal whitespace", `KEY="  hello  "` + "\n", map[string]string{"KEY": "  hello  "}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, err := Parse(strings.NewReader(tc.in))
			if err != nil {
				t.Fatalf("Parse: %v", err)
			}
			if !reflect.DeepEqual(got, tc.want) {
				t.Fatalf("got %+v, want %+v", got, tc.want)
			}
		})
	}
}
