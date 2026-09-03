#!/usr/bin/env bash
# Cut a GitHub Release. Replaces .github/workflows/release.yml (GitHub Actions
# retired 2026-09-03), which fired on a v*.*.* tag and called
# softprops/action-gh-release. `gh release create` does the same thing.
#
#   scripts/release.sh v1.2.3 [--notes "..."]
#
# With no --notes, GitHub generates them from the commits since the last tag.
set -euo pipefail
tag="${1:?usage: scripts/release.sh vX.Y.Z [--notes \"...\"]}"; shift || true
case "$tag" in v*.*.*) ;; *) echo "release: tag must look like v1.2.3" >&2; exit 1 ;; esac

scripts/ci-gates.sh
git tag -a "$tag" -m "$tag"
git push origin "$tag"
if [ "${1:-}" = "--notes" ]; then
  gh release create "$tag" --title "$tag" --notes "${2:?--notes needs text}"
else
  gh release create "$tag" --title "$tag" --generate-notes
fi
