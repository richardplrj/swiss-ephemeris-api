#!/usr/bin/env bash
# Download the bundled Swiss Ephemeris data files (~6 MB) into ./ephe.
# Covers 1200 AD – 3000 AD at full 0.001" precision for Sun–Pluto, Moon, the
# main asteroids (Ceres/Pallas/Juno/Vesta), Chiron/Pholus, plus ~800 fixed stars.
#
# These files are already committed to the repo; this script only exists to
# reproduce/refresh them. Source: github.com/aloistr/swisseph (© Astrodienst AG).
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)/ephe"
BASE="https://raw.githubusercontent.com/aloistr/swisseph/master/ephe"
mkdir -p "$DIR"
cd "$DIR"

FILES=(
  sepl_12.se1 semo_12.se1 seas_12.se1   # 1200–1799 AD
  sepl_18.se1 semo_18.se1 seas_18.se1   # 1800–2399 AD
  sepl_24.se1 semo_24.se1 seas_24.se1   # 2400–2999 AD
  sefstars.txt                          # fixed stars
  seleapsec.txt                         # leap seconds
)

for f in "${FILES[@]}"; do
  echo "downloading $f"
  curl -sSL --fail -o "$f" "$BASE/$f"
done

echo "done -> $DIR"
du -sh "$DIR"
