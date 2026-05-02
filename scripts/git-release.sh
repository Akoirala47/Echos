#!/usr/bin/env bash
# Bump echos/version.py, commit all tracked + new files, annotated tag, push.
# Usage:
#   ./scripts/git-release.sh 2.3.5 'fix: describe the release'
#
# Omit the leading "v" from the version argument; the git tag will be v2.3.5.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ver="${1:?version e.g. 2.3.5}"
ver="${ver#v}"
msg="${2:?commit message}"

export _ECHOS_REL_VER="$ver"
python3 -c "
from pathlib import Path
import os, re
ver = os.environ['_ECHOS_REL_VER']
p = Path('echos/version.py')
text = p.read_text()
text2, n = re.subn(
    r'^APP_VERSION = \"[^\"]+\"',
    f'APP_VERSION = \"{ver}\"',
    text,
    count=1,
    flags=re.M,
)
if n != 1:
    raise SystemExit('Could not patch APP_VERSION in echos/version.py')
p.write_text(text2)
"

git add -A
git commit -m "$msg"
git tag -a "v$ver" -m "Release v$ver"
git push origin HEAD
git push origin "v$ver"
