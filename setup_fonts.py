"""
Stáhne DM Sans, DM Mono a DM Serif Display TTF z Google Fonts GitHub repa
do složky ./fonts/. Stačí spustit jednou:

    python3 setup_fonts.py

Soubory pak commitni do repa, ať je má i Streamlit Cloud.
Závislosti: jen standardní knihovna (urllib).
"""
from __future__ import annotations

import os
import sys
import urllib.request
import urllib.error

# Stabilní URL na Google Fonts GitHub mirror (OFL licence — bundle povolen).
# Variabilní DM Sans má všechny váhy v jednom souboru, DM Mono / DM Serif Display
# jsou klasické statické fonty.
FONTS = [
    # (název cíle, URL ke stažení)
    ("DMSans-Variable.ttf",
     "https://github.com/google/fonts/raw/main/ofl/dmsans/DMSans%5Bopsz%2Cwght%5D.ttf"),
    ("DMMono-Regular.ttf",
     "https://github.com/google/fonts/raw/main/ofl/dmmono/DMMono-Regular.ttf"),
    ("DMMono-Medium.ttf",
     "https://github.com/google/fonts/raw/main/ofl/dmmono/DMMono-Medium.ttf"),
    ("DMSerifDisplay-Regular.ttf",
     "https://github.com/google/fonts/raw/main/ofl/dmserifdisplay/DMSerifDisplay-Regular.ttf"),
]


def download(url: str, dst: str) -> int:
    """Stáhne URL do dst. Vrací počet bajtů, raise při chybě."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "sprint-analytics-setup-fonts/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    with open(dst, "wb") as f:
        f.write(data)
    return len(data)


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    fonts_dir = os.path.join(here, "fonts")
    os.makedirs(fonts_dir, exist_ok=True)

    print(f"📦 Stahuji fonty do {fonts_dir}\n")
    failed = 0
    skipped = 0
    for name, url in FONTS:
        dst = os.path.join(fonts_dir, name)
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            print(f"⏭  {name} (už existuje, přeskakuji)")
            skipped += 1
            continue
        try:
            size = download(url, dst)
            print(f"✅ {name} ({size // 1024} kB)")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"❌ {name}: {e}")
            failed += 1

    total = len(FONTS)
    ok = total - failed - skipped
    print(f"\n— Hotovo: {ok} staženo, {skipped} přeskočeno, {failed} chyba —")
    if failed > 0:
        return 1
    print(f"\nDalší krok: commitni složku fonts/ do repa "
          "(otevři upload_to_github.py — má seznam souborů — a doplň tam fonts/*.ttf).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
