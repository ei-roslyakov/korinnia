#!/bin/sh
# Regenerate frontend/public/third-party-notices.txt: the licences of the open-source
# packages and fonts bundled into the web app (their notices must travel with copies), plus
# a list of the backend's Python packages (whose licence files ship inside the image).
# Usage: make notices
set -eu
cd "$(dirname "$0")/.."
OUT=frontend/public/third-party-notices.txt

docker run --rm -v "$PWD/frontend":/w -v korinnia_frontend-node-modules:/w/node_modules -w /w \
  node:24-alpine sh -c '
    npx --yes license-checker-rseidelsohn@4 --production --excludePrivatePackages --json \
      > /tmp/licenses.json 2>/dev/null
    node -e "
      const fs = require(\"fs\");
      const all = JSON.parse(fs.readFileSync(\"/tmp/licenses.json\", \"utf8\"));
      for (const [pkg, info] of Object.entries(all).sort()) {
        console.log(pkg + \"  (\" + info.licenses + \")\");
        if (info.repository) console.log(info.repository);
        let text = \"\";
        try { text = fs.readFileSync(info.licenseFile, \"utf8\").trim(); } catch {}
        if (text && !/readme/i.test(info.licenseFile || \"\")) console.log(\"\n\" + text);
        console.log(\"\n\" + \"-\".repeat(78) + \"\n\");
      }
    "
  ' > /tmp/korinnia-frontend-notices.txt

docker compose run --rm --no-deps -T backend sh -c '
  uv pip install --quiet --no-cache --target /tmp/pl pip-licenses >/dev/null 2>&1
  PYTHONPATH=/tmp/pl python -m piplicenses --from=mixed --format=plain-vertical --with-urls \
    --ignore-packages pip-licenses prettytable wcwidth
' > /tmp/korinnia-backend-notices.txt 2>/dev/null

{
  echo "Korinnia: third-party software notices"
  echo "======================================="
  echo
  echo "Korinnia is Copyright (c) 2026 Yevhenii Rosliakov, licensed under the GNU AGPL-3.0 (see LICENSE)."
  echo "It includes the following open-source components, each under its own licence."
  echo "Map data (c) OpenStreetMap contributors (ODbL), shown on the map itself."
  echo
  echo "Web application (JavaScript packages and fonts bundled into the browser app)"
  echo "---------------------------------------------------------------------------"
  echo
  cat /tmp/korinnia-frontend-notices.txt
  echo
  echo "Server (Python packages; their licence files are included in the server image)"
  echo "------------------------------------------------------------------------------"
  echo
  cat /tmp/korinnia-backend-notices.txt
} > "$OUT"
rm -f /tmp/korinnia-frontend-notices.txt /tmp/korinnia-backend-notices.txt
echo "wrote $OUT ($(wc -l < "$OUT") lines)"
