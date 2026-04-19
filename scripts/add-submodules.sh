#!/usr/bin/env bash
# scripts/add-submodules.sh — wire submodules from the
# HelixDevelopment and vasic-digital orgs (or any git host) under
# third_party/. Non-interactive, credentials come from the
# environment (SSH agent or GIT_ASKPASS).
#
# Manifest formats (one per line):
#   org/repo
#   org/repo path/override
#   provider:org/repo            (provider: github or gitlab, default github)
#
# Feed the manifest via stdin or SUBMODULE_MANIFEST env var:
#
#   printf 'HelixDevelopment/core\nvasic-digital/shared\n' | ./scripts/add-submodules.sh
#
#   SUBMODULE_MANIFEST=$'HelixDevelopment/core\nvasic-digital/shared' \
#       ./scripts/add-submodules.sh

set -euo pipefail

print_info()    { printf '\033[0;34m[INFO]\033[0m %s\n' "$*"; }
print_success() { printf '\033[0;32m[ OK ]\033[0m %s\n' "$*"; }
print_warning() { printf '\033[0;33m[WARN]\033[0m %s\n' "$*"; }
print_error()   { printf '\033[0;31m[FAIL]\033[0m %s\n' "$*" >&2; }

manifest=""
if [[ -n "${SUBMODULE_MANIFEST:-}" ]]; then
    manifest="$SUBMODULE_MANIFEST"
elif [[ -p /dev/stdin ]]; then
    manifest="$(cat)"
else
    print_error "no manifest. Provide via SUBMODULE_MANIFEST or stdin."
    exit 2
fi

mkdir -p third_party

while IFS= read -r line; do
    line="${line%%#*}"                       # strip comments
    line="$(echo "$line" | xargs)"           # trim
    [[ -z "$line" ]] && continue

    provider="github"
    if [[ "$line" == *:* ]]; then
        provider="${line%%:*}"
        line="${line#*:}"
    fi

    repo_part="$(echo "$line" | awk '{print $1}')"
    override="$(echo "$line" | awk '{print $2}')"
    if [[ "$repo_part" != */* ]]; then
        print_warning "skipping malformed line: $line"
        continue
    fi
    org="${repo_part%%/*}"
    repo="${repo_part##*/}"
    case "$provider" in
        github) url="git@github.com:$org/$repo.git" ;;
        gitlab) url="git@gitlab.com:$org/$repo.git" ;;
        *) print_error "unknown provider: $provider"; exit 3 ;;
    esac
    dest="third_party/${override:-$repo}"
    if [[ -d "$dest/.git" ]] || git submodule status "$dest" 2>/dev/null | grep -q .; then
        print_info "already present: $dest"
        continue
    fi
    print_info "adding $url -> $dest"
    git submodule add "$url" "$dest"
done <<< "$manifest"

git submodule update --init --recursive
print_success "submodules synchronised"
