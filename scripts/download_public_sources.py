"""Télécharge les sources publiques brutes (GeoNames + MeSH NLM) dans data/raw/.

Ces fichiers ne sont pas redistribués dans le dépôt (volumineux). Ce script les récupère
depuis leurs sources officielles. La traduction française bilingue MeSH (Inserm) n'a pas de
lien public stable et doit être obtenue séparément (voir data/README.md).

Usage:
    python scripts/download_public_sources.py
"""
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

# Sources publiques officielles. Les URLs MeSH NLM changent d'année en année
# (desc/supp <ANNÉE>) ; adaptez si besoin.
SOURCES = [
    ("https://download.geonames.org/export/dump/allCountries.zip",
     RAW / "geonames" / "allCountries.zip"),
    ("https://download.geonames.org/export/dump/alternateNamesV2.zip",
     RAW / "geonames" / "alternateNamesV2.zip"),
    ("https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc2026.xml",
     RAW / "mesh" / "desc2026.xml"),
    ("https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/supp2026.xml",
     RAW / "mesh" / "supp2026.xml"),
]


def _progress(done: int, total: int) -> None:
    if total > 0:
        pct = min(100, done * 100 // total)
        sys.stdout.write(f"\r    {pct:3d}%  ({done // (1024*1024)} / {total // (1024*1024)} Mo)")
        sys.stdout.flush()


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[skip] {dest.name} déjà présent")
        return
    print(f"[get ] {url}")
    with urllib.request.urlopen(url) as r:
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        with open(dest, "wb") as f:
            while True:
                chunk = r.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                _progress(done, total)
    print(f"\n       -> {dest}")


def main() -> None:
    for url, dest in SOURCES:
        try:
            download(url, dest)
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {url}\n       {e}\n       Téléchargez manuellement vers {dest}")
    print("\nRappel : la traduction MeSH bilingue FR/EN (Inserm) "
          "n'est pas téléchargée ici (voir data/README.md).")
    print("Ensuite : python scripts/build_geonames_index.py "
          "&& python scripts/build_mesh_index.py")


if __name__ == "__main__":
    main()
