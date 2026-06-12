"""Build GeoNames lookup index from raw data using SQLite.

Parses allCountries.zip and alternateNamesV2.zip to create a SQLite
database for efficient name -> geonameid lookups.

Output: data/processed/geonames.db
"""

import sqlite3
import zipfile
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "geonames"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

ALL_COUNTRIES_ZIP = RAW_DIR / "allCountries.zip"
ALT_NAMES_ZIP = RAW_DIR / "alternateNamesV2.zip"


def create_schema(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS locations (
            geonameid TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            asciiname TEXT,
            country_code TEXT,
            feature_class TEXT,
            feature_code TEXT,
            population INTEGER DEFAULT 0,
            admin1 TEXT,
            latitude REAL,
            longitude REAL
        );

        CREATE TABLE IF NOT EXISTS names (
            name_lower TEXT NOT NULL,
            geonameid TEXT NOT NULL,
            lang TEXT DEFAULT '',
            FOREIGN KEY (geonameid) REFERENCES locations(geonameid)
        );

        CREATE INDEX IF NOT EXISTS idx_names_lower ON names(name_lower);
    """)


def load_all_countries(conn: sqlite3.Connection, zip_path: Path):
    """Parse allCountries.txt and insert locations + name variants."""
    batch_loc = []
    batch_names = []
    count = 0

    with zipfile.ZipFile(zip_path) as z:
        with z.open("allCountries.txt") as f:
            for line in f:
                fields = line.decode("utf-8", errors="replace").strip().split("\t")
                if len(fields) < 19:
                    continue

                gid = fields[0]
                name = fields[1]
                ascii_name = fields[2]
                alt_names = fields[3]
                lat = float(fields[4]) if fields[4] else None
                lon = float(fields[5]) if fields[5] else None
                fc = fields[6]
                fcode = fields[7]
                cc = fields[8]
                admin1 = fields[10]
                pop = int(fields[14]) if fields[14] else 0

                batch_loc.append((gid, name, ascii_name, cc, fc, fcode, pop, admin1, lat, lon))

                seen = set()
                for n in [name, ascii_name]:
                    nl = n.lower().strip()
                    if nl and nl not in seen:
                        batch_names.append((nl, gid, ""))
                        seen.add(nl)

                if alt_names:
                    for alt in alt_names.split(","):
                        alt = alt.strip()
                        al = alt.lower()
                        if al and al not in seen:
                            batch_names.append((al, gid, ""))
                            seen.add(al)

                count += 1
                if count % 500_000 == 0:
                    conn.executemany(
                        "INSERT OR IGNORE INTO locations VALUES (?,?,?,?,?,?,?,?,?,?)",
                        batch_loc,
                    )
                    conn.executemany("INSERT INTO names VALUES (?,?,?)", batch_names)
                    conn.commit()
                    batch_loc.clear()
                    batch_names.clear()
                    print(f"    {count:,} locations processed...")

    if batch_loc:
        conn.executemany(
            "INSERT OR IGNORE INTO locations VALUES (?,?,?,?,?,?,?,?,?,?)", batch_loc
        )
        conn.executemany("INSERT INTO names VALUES (?,?,?)", batch_names)
        conn.commit()

    print(f"  -> {count:,} total locations loaded")


def load_alternate_names_fr(conn: sqlite3.Connection, zip_path: Path):
    """Parse alternateNamesV2.txt, inserting only French alternate names."""
    batch = []
    count = 0

    with zipfile.ZipFile(zip_path) as z:
        with z.open("alternateNamesV2.txt") as f:
            for line in f:
                fields = line.decode("utf-8", errors="replace").strip().split("\t")
                if len(fields) < 4:
                    continue
                if fields[2] != "fr":
                    continue

                gid = fields[1]
                name = fields[3].strip()
                if not name:
                    continue

                batch.append((name.lower(), gid, "fr"))
                count += 1

                if count % 100_000 == 0:
                    conn.executemany("INSERT INTO names VALUES (?,?,?)", batch)
                    conn.commit()
                    batch.clear()

    if batch:
        conn.executemany("INSERT INTO names VALUES (?,?,?)", batch)
        conn.commit()

    print(f"  -> {count:,} French alternate names loaded")


def verify_with_training(conn: sqlite3.Connection):
    """Check that all training GeoNames IDs exist in the index."""
    import json

    train_path = Path(__file__).resolve().parent.parent / "data" / "protected" / "train_evalLLM.json"
    with open(train_path, encoding="utf-8") as f:
        train = json.load(f)

    found, total = 0, 0
    missing = []
    for doc in train:
        for ent in doc.get("entities", []):
            if ent["source"] != "GeoNames":
                continue
            total += 1
            gid = ent["id_kb"]
            row = conn.execute(
                "SELECT name FROM locations WHERE geonameid = ?", (gid,)
            ).fetchone()
            if row:
                found += 1
            else:
                missing.append((ent["text"], gid))

    print(f"  ID lookup: {found}/{total} training IDs found")

    name_found, name_total = 0, 0
    for doc in train:
        for ent in doc.get("entities", []):
            if ent["source"] != "GeoNames":
                continue
            name_total += 1
            text = ent["text"].lower()
            rows = conn.execute(
                "SELECT DISTINCT n.geonameid FROM names n WHERE n.name_lower = ?",
                (text,),
            ).fetchall()
            gids = {r[0] for r in rows}
            if ent["id_kb"] in gids:
                name_found += 1
            else:
                all_gids = [r[0] for r in rows[:5]]
                missing.append(
                    (ent["text"], ent["id_kb"], f"candidates={all_gids}")
                )

    print(f"  Name->ID lookup: {name_found}/{name_total} training mentions resolve correctly")
    if name_found < name_total:
        unique_missing = list(set(missing))[:10]
        for m in unique_missing:
            print(f"    MISS: {m}")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    db_path = OUT_DIR / "geonames.db"

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-256000")

    print("Building GeoNames SQLite index...")
    create_schema(conn)

    print("Loading allCountries.zip...")
    load_all_countries(conn, ALL_COUNTRIES_ZIP)

    print("Loading French alternate names...")
    load_alternate_names_fr(conn, ALT_NAMES_ZIP)

    loc_count = conn.execute("SELECT COUNT(*) FROM locations").fetchone()[0]
    name_count = conn.execute("SELECT COUNT(*) FROM names").fetchone()[0]
    print(f"\nDatabase stats: {loc_count:,} locations, {name_count:,} name entries")

    size_mb = db_path.stat().st_size / (1024 * 1024)
    print(f"Saved to {db_path} ({size_mb:.1f} MB)")

    train_path = Path(__file__).resolve().parent.parent / "train_evalLLM.json"
    if train_path.exists():
        print("\nVerification with training data...")
        verify_with_training(conn)
    else:
        print("\nSkipping training verification (train_evalLLM.json not found).")

    conn.close()


if __name__ == "__main__":
    main()
