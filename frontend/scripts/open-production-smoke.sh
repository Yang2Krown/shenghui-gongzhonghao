#!/usr/bin/env bash
set -euo pipefail

target_url="${SMOKE_TARGET_URL:-}"
if [[ -z "$target_url" ]]; then
  echo "Set SMOKE_TARGET_URL first, for example: SMOKE_TARGET_URL=https://gzh.midonghub.com npm run smoke:production" >&2
  exit 2
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "npx is required for the production browser smoke." >&2
  exit 1
fi

target_url="${target_url%/}"
session_name="${SMOKE_SESSION_NAME:-gzh-practical-upload}"
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
artifact_dir="$repo_root/output/playwright/practical-upload"
mkdir -p "$artifact_dir"
cd "$artifact_dir"

pwcli() {
  npx --yes --package @playwright/cli playwright-cli --session "$session_name" "$@"
}

pwcli open "$target_url/creation/practical" --headed
echo "Sign in with the intended real account, then press Enter to continue."
read -r

pwcli open "$target_url/creation/practical"
pwcli snapshot
pwcli eval "(() => {
  const zones = [...document.querySelectorAll('[data-testid^=\"brief-upload-dropzone-\"]')];
  if (!zones.length) throw new Error('No brief upload zone found');
  const invalid = zones.find((zone) => {
    const style = getComputedStyle(zone);
    return style.display !== 'flex' || zone.getBoundingClientRect().height < 104;
  });
  if (invalid) throw new Error('Brief upload zone layout contract failed');
  return JSON.stringify({ count: zones.length, labels: zones.map((zone) => zone.getAttribute('aria-label')) });
})()"

echo "Manually verify each upload zone opens a native chooser, then Tab + Enter/Space on the first zone. Cancel every chooser; do not submit an actual brief. Press Enter after checking."
read -r

pwcli console
pwcli network
pwcli screenshot
echo "Smoke artifacts are under $artifact_dir. Review console/network output and the screenshot before recording a production pass."
