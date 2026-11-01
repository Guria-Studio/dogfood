#!/usr/bin/env bash
# Construye la SPA del panel: deja el build en src/dogfood/panel/estatico/.
set -euo pipefail
cd "$(dirname "$0")/../web"
npm ci
npm run gen:api
npm run build
