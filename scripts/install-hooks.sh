#!/usr/bin/env bash
# Устанавливает локальные git-хуки из scripts/hooks/ в .git/hooks/.
# Запуск (однократно после клона): bash scripts/install-hooks.sh
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
SRC="$REPO_ROOT/scripts/hooks"
DST="$REPO_ROOT/.git/hooks"

if [ ! -d "$SRC" ]; then
    echo "install-hooks: нет каталога $SRC" >&2
    exit 1
fi

mkdir -p "$DST"
for hook in "$SRC"/*; do
    name="$(basename "$hook")"
    cp "$hook" "$DST/$name"
    chmod +x "$DST/$name"
    echo "install-hooks: установлен $name -> $DST/$name"
done

echo "install-hooks: готово."
