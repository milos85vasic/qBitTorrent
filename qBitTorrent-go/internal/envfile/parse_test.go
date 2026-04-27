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
