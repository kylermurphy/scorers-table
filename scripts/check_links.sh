#!/usr/bin/env bash
# Fails if the built site has a broken internal link, image, script or in-page anchor (html-proofer 5).
# Checks every page under _site/, the /preview/ copy included. Links to other sites (a league's contact page,
# the calendar subscribe buttons) are NOT checked: the build must not depend on the internet.
#
# Run it after `bundle exec jekyll build` and scripts/build_preview.sh, from the repo root:
#   scripts/check_links.sh [folder]        # default folder: _site
#
# Environment: BASE_PATH is where the site lives on its host ("" or "/repo-name", no trailing slash). Links in
# the built pages start with it but the files in _site/ do not, so it is stripped before the check.
set -euo pipefail
cd "$(dirname "$0")/.."

site="${1:-_site}"
base_path="${BASE_PATH:-}"
if [ ! -d "$site" ]; then
  echo "Nothing to check: $site/ does not exist. Build the site first (bundle exec jekyll build)." >&2
  exit 2
fi
if [ -n "$base_path" ] && { [ "${base_path:0:1}" != "/" ] || [ "${base_path: -1}" = "/" ]; }; then
  echo "BASE_PATH must be empty or start with / and not end with / (like /my-league), not '$base_path'" >&2
  exit 2
fi

args=("$site" --checks "Links,Images,Scripts" --disable-external --no-allow-missing-href --no-enforce-https)
if [ -n "$base_path" ]; then
  # html-proofer takes "regexp:replacement" pairs; escape the characters a regexp would read as syntax.
  pattern=$(printf '%s' "$base_path" | sed 's/[][\.*^$+?(){}|]/\\&/g')
  args+=(--swap-urls "^${pattern}:")
fi

LC_ALL=C.UTF-8 bundle exec htmlproofer "${args[@]}"
