#!/usr/bin/env bash
# The sample copy of the site at /preview/: the same pages, built from the made-up sample season, into
# _site/preview/ (published at <site>/preview/, with the sample banner that links back to the live site).
# Nothing links to it and every page carries the noindex tag (unless league.yml allows search engines).
#
# Run it from the repo root after the main `bundle exec jekyll build`, which would otherwise wipe it:
#   scripts/build_preview.sh
#
# It does nothing when league.yml says `preview: false`, or `sample_data: true` (then the main site already
# shows the sample season).
#
# Environment (all optional; the CI workflow sets them from actions/configure-pages):
#   BASE_PATH    where the site lives on its host: "" or "/repo-name" (no trailing slash). Default: "".
#   SITE_ORIGIN  the site's origin, like https://owner.github.io. Default: "" (links stay relative).
#   JEKYLL_ENV   default: production.
#
# How it works (spec section 4.3): `build.py --sample` rewrites _data/computed/, the stub pages and calendar/
# for the sample season; Jekyll then builds into _site/preview/ with baseurl "<BASE_PATH>/preview"; finally
# `build.py` runs again for the real data, so a local checkout is left as it was (this also happens when
# Jekyll fails).
set -euo pipefail
cd "$(dirname "$0")/.."

base_path="${BASE_PATH:-}"
origin="${SITE_ORIGIN:-}"
if [ -n "$base_path" ] && { [ "${base_path:0:1}" != "/" ] || [ "${base_path: -1}" = "/" ]; }; then
  echo "BASE_PATH must be empty or start with / and not end with / (like /my-league), not '$base_path'" >&2
  exit 2
fi

read -r preview sample <<<"$(python3 -c 'import yaml; c = yaml.safe_load(open("league.yml")) or {}; print(c.get("preview", True), c.get("sample_data", False))')"
if [ "$preview" != "True" ] || [ "$sample" = "True" ]; then
  echo "Preview copy: skipped (preview: $preview, sample_data: $sample in league.yml)"
  exit 0
fi

# The build.py flags for the real site and for the preview. --site-url is only given when the origin is known.
main_args=()
preview_args=(--sample)
if [ -n "$origin" ]; then
  main_args+=(--site-url "$origin$base_path")
  preview_args+=(--site-url "$origin$base_path/preview")
fi

tmp=$(mktemp -d)
restore=0
cleanup() {
  local status=$?
  rm -rf "$tmp"
  if [ "$restore" = 1 ]; then
    # Back to the real season's data (quietly: the main build already printed its report).
    python3 scripts/build.py ${main_args[@]+"${main_args[@]}"} >/dev/null || status=$?
  fi
  exit "$status"
}
trap cleanup EXIT

# Laid over _config.yml: the preview lives under /preview of the site.
printf 'url: "%s"\nbaseurl: "%s/preview"\n' "$origin" "$base_path" >"$tmp/preview-config.yml"

restore=1
python3 scripts/build.py "${preview_args[@]}"
JEKYLL_ENV="${JEKYLL_ENV:-production}" bundle exec jekyll build \
  --config "_config.yml,$tmp/preview-config.yml" --destination _site/preview
echo "Preview copy: _site/preview/ (sample season)"
