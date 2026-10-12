#!/usr/bin/env bash
# One-time setup for a fresh clone: git runs the harness check before each commit.
set -euo pipefail
cd "$(dirname "$0")"
hook="$(git rev-parse --git-path hooks/pre-commit)"
if [ -e "$hook" ] && ! grep -q 'verify.sh' "$hook"; then
  echo "setup: $hook already exists and is not ours; left alone" >&2
  exit 1
fi
printf '#!/usr/bin/env bash\nexec "$(git rev-parse --show-toplevel)/.claude/verify.sh"\n' > "$hook"
chmod +x "$hook"
echo "setup: pre-commit hook installed at $hook"
