#!/usr/bin/env bash
# Dry-run the overlay against an upstream RustDesk tag on this machine (no GitHub, no build): clone, apply.py,
# make_workflow.py, show what changed. Usage: ./test-local.sh [tag] [logo.png] [work dir]
#   ./test-local.sh 1.5.0 assets/logo.png /tmp/chantch-overlay-test
# Uses brand.env from this folder; if RS_PUB_KEY is still empty there, a throwaway key is used for the test only.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
tag="${1:-$(git ls-remote --tags https://github.com/rustdesk/rustdesk | awk -F/ '{print $3}' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)}"
logo="${2:-$here/assets/logo.png}"
work="${3:-$(mktemp -d)}"
python3 -c 'import PIL' 2>/dev/null || { echo "needs Pillow: python3 -m pip install pillow"; exit 2; }
[[ -f "$logo" ]] || { echo "logo not found: $logo (assets/README.md)"; exit 2; }
logo="$(cd "$(dirname "$logo")" && pwd)/$(basename "$logo")"
mkdir -p "$work"; cd "$work"
rm -rf src && git -c advice.detachedHead=false clone -q --depth 1 --branch "$tag" --recurse-submodules --shallow-submodules https://github.com/rustdesk/rustdesk src
brand="$here/brand.env"
if grep -q '^RS_PUB_KEY=$' "$brand"; then
  sed 's|^RS_PUB_KEY=$|RS_PUB_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=|' "$brand" > brand.test.env; brand="$work/brand.test.env"
  echo "(RS_PUB_KEY empty in brand.env: using a throwaway key for this test)"
fi
python3 "$here/apply.py" --src src --brand "$brand" --logo "$logo"
python3 "$here/make_workflow.py" --src src --brand "$brand" --release-tag "${tag}-chantch.0"
git -C src status --short | head -40
git -C src/libs/hbb_common diff --stat
echo "work dir: $work (look at the icons in src/res/)"
