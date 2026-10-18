#!/usr/bin/env bash
# The sample copies of the site, built after the real one into _site/:
#
#   _site/preview/   the league's own site (name, colours, logo, look) with made-up games, when league.yml says
#                    `preview: true` and the real data is showing (`sample_data: false`). The banner links back to
#                    the live site. A league whose data/seasons.yml lists no sample season gets no /preview/: the
#                    script says so in one line and carries on (the sport previews below are not affected). Also no
#                    /preview/ while `landing_page: true`: the root is then the landing page, there is no league
#                    site to preview, and the script says so in one line.
#   _site/<sport>/   one demo copy per sport named by `sport_previews` in league.yml (true, or a list of sport ids;
#                    false builds none): the template's made-up league for that sport (sports/<sport>/sample.py)
#                    in the sport's own look. Always built, whatever `preview` and `sample_data` say. While
#                    `landing_page: true` the landing page (the root of _site/, built by the main Jekyll build with
#                    _config.landing.yml) links to them, and each demo's banner says "All sports" (a link to the
#                    landing page) instead of "Go to the live site" (`live_landing: true` in the copy's overlay).
#
# Nothing links to them from the league's own pages and every page carries the noindex tag (a sport copy always
# does; /preview/ unless league.yml allows search engines). See docs/stage-5-basketball-spec.md, section 7.
#
# Run it from the repo root after the main `bundle exec jekyll build`, which would otherwise wipe them:
#   scripts/build_preview.sh
#
# Environment (all optional; the CI workflow sets them from actions/configure-pages):
#   BASE_PATH    where the site lives on its host: "" or "/repo-name" (no trailing slash). Default: "".
#   SITE_ORIGIN  the site's origin, like https://owner.github.io. Default: "" (links stay relative).
#   JEKYLL_ENV   default: production.
#
# How it works: for each copy, `build.py` rewrites _data/computed/ and the stub pages (and calendar/) in the Jekyll
# source folder, then Jekyll builds into _site/<copy>/ with baseurl "<BASE_PATH>/<copy>" and `live_baseurl`
# "<BASE_PATH>" (where the live site is, for the banner's links). A sport copy reads a temporary root written by
# scripts/preview_root.py (the sport's sample league and sample seasons, nothing of the real league). The copies share
# the source folder, so they are built one after another. Finally `build.py` runs again for the real data, so a local
# checkout is left as it was (this also happens when a step fails, or the script is interrupted): the restore is the
# plain `build.py` again, which also puts back landing.json and _config.landing.yml (the copies' builds swap
# _data/computed/ whole, but they never use the landing overlay: _config.yml leaves landing/ out of every copy).
set -euo pipefail
cd "$(dirname "$0")/.."

base_path="${BASE_PATH:-}"
origin="${SITE_ORIGIN:-}"
if [ -n "$base_path" ] && { [ "${base_path:0:1}" != "/" ] || [ "${base_path: -1}" = "/" ]; }; then
  echo "BASE_PATH must be empty or start with / and not end with / (like /my-league), not '$base_path'" >&2
  exit 2
fi

read -r preview sample landing <<<"$(python3 -c 'import yaml; c = yaml.safe_load(open("league.yml")) or {}; print(c.get("preview", True), c.get("sample_data", False), c.get("landing_page", False) is True)')"
league_copy=0
if [ "$landing" = "True" ]; then
  echo "landing_page: true: skipping /preview/ (the root is the landing page, there is no league site to preview)"
elif [ "$preview" = "True" ] && [ "$sample" != "True" ]; then
  league_copy=1
  # A league that took its sample seasons out of data/seasons.yml has nothing to build /preview/ from: skip it (the
  # sport previews do not need them). Only "no season there is marked `sample: true`" skips; a file that cannot be read
  # or a sample season that is broken is left for build.py to report, as before.
  has_sample=$(python3 -c '
import yaml
try:
    seasons = yaml.safe_load(open("data/seasons.yml"))
except Exception:
    seasons = None
print("yes" if not isinstance(seasons, list) or any(isinstance(s, dict) and s.get("sample") for s in seasons) else "no")')
  if [ "$has_sample" = "no" ]; then
    echo "no sample season in data/seasons.yml: skipping /preview/"
    league_copy=0
  fi
fi
# The sport ids sport_previews asks for (checked: a problem in league.yml stops here with its message).
sport_ids=$(python3 scripts/preview_root.py --list)
if [ "$league_copy" = 0 ] && [ -z "$sport_ids" ]; then
  echo "Preview copies: none (preview: $preview, sample_data: $sample, no sport_previews in league.yml)"
  exit 0
fi

# The build.py flags for the real site (the restore at the end) and for each copy. --site-url is only given when the
# origin is known.
main_args=()
if [ -n "$origin" ]; then
  main_args+=(--site-url "$origin$base_path")
fi

tmp=$(mktemp -d)
restore=0
cleanup() {
  local status=$?
  trap - EXIT
  if [ "$restore" = 1 ]; then
    # Back to the real season's data. Its report was printed by the main build; show it again only if it fails.
    local restore_status=0
    python3 scripts/build.py ${main_args[@]+"${main_args[@]}"} >"$tmp/restore-report.txt" 2>&1 || restore_status=$?
    if [ "$restore_status" != 0 ]; then
      status=$restore_status
      cat "$tmp/restore-report.txt" >&2
    fi
  fi
  rm -rf "$tmp"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# One copy: $1 = its folder under _site/, the rest = the build.py flags. Laid over _config.yml: the copy lives under
# /<folder> of the site, and the live site (for the banner) is at the site's base path.
build_copy() {
  local folder="$1"; shift
  printf 'url: "%s"\nbaseurl: "%s/%s"\nlive_baseurl: "%s"\n' "$origin" "$base_path" "$folder" "$base_path" \
    >"$tmp/$folder-config.yml"
  if [ "$landing" = "True" ]; then
    printf 'live_landing: true\n' >>"$tmp/$folder-config.yml"          # the banner's link says "All sports"
  fi
  # The "Still to decide" list is the real league's business, not a copy's: show a copy's report only if it fails.
  if python3 scripts/build.py "$@" >"$tmp/$folder-report.txt" 2>&1; then
    tail -n 1 "$tmp/$folder-report.txt"
  else
    local status=$?
    cat "$tmp/$folder-report.txt" >&2
    return "$status"
  fi
  JEKYLL_ENV="${JEKYLL_ENV:-production}" bundle exec jekyll build \
    --config "_config.yml,$tmp/$folder-config.yml" --destination "_site/$folder"
}

restore=1
if [ "$league_copy" = 1 ]; then
  site_args=()
  [ -n "$origin" ] && site_args+=(--site-url "$origin$base_path/preview")
  build_copy preview --sample ${site_args[@]+"${site_args[@]}"}
  echo "Preview copy: _site/preview/ (sample season)"
fi
for id in $sport_ids; do
  python3 scripts/preview_root.py "$id" "$tmp/root-$id"
  build_copy "$id" --root "$tmp/root-$id" --out . --sport-preview "$id"
  rm -rf "$tmp/root-$id"
  echo "Sport preview copy: _site/$id/ (the $id sample league)"
done
