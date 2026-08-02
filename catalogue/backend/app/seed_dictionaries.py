#!/usr/bin/env python3
"""Seeds organ/tissue/species/stain dictionaries (plus the organ-tissue
relationships between them) from seed_data/dictionaries.json - a real,
curated controlled vocabulary (77 organs, 39 tissues, 50 species, 257
stains, 49 organ-tissue relationships at time of writing), not sample/demo
data. Unlike seed_example_data.py, this is worth running on a real
deployment too, not just for local testing - starting from a real curated
vocabulary rather than an empty dictionary means search/correction-form
dropdowns are useful from day one.

Uses natural keys (organ_name, tissue_name, species_name, original_stain)
throughout - the surrogate *_id columns in the JSON are the source
database's own auto-increment values and are never used here; this
database assigns its own on insert. Safe to re-run - skips anything that
already exists by natural key, and the organ_tissue relationship import
looks up organ_id/tissue_id fresh by name rather than trusting the JSON's
own ids.

Run inside the backend container, after 0000_initial_schema.sql and the
000N_*.sql migrations have been applied:

    docker exec -it catalogue_backend python3 /app/app/seed_dictionaries.py
"""

import json
import os
import sys

import pymysql

DICTIONARIES_JSON = os.path.join(
    os.path.dirname(__file__), "seed_data", "dictionaries.json"
)


def get_db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "catalogue_mariadb"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def seed_simple_dictionary(cur, table, name_column, id_column, rows):
    """organ/tissue/species share this exact shape - one INSERT per row,
    skip by natural key, drop the source database's own surrogate id."""
    created = 0
    for row in rows:
        row = {k: v for k, v in row.items() if k != id_column}
        cur.execute(
            f"SELECT {id_column} FROM {table} WHERE {name_column} = %s",
            (row[name_column],),
        )
        if cur.fetchone():
            continue
        columns = list(row.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        cur.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            [row[c] for c in columns],
        )
        created += 1
    print(f"{table}: {created} created, {len(rows) - created} already present.")


def seed_stain_dictionary(cur, rows):
    """stain_dictionary's own primary key IS the natural key
    (original_stain), no surrogate id to drop."""
    created = 0
    for row in rows:
        cur.execute(
            "SELECT 1 FROM stain_dictionary WHERE original_stain = %s",
            (row["original_stain"],),
        )
        if cur.fetchone():
            continue
        columns = list(row.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        cur.execute(
            f"INSERT INTO stain_dictionary ({', '.join(columns)}) VALUES ({placeholders})",
            [row[c] for c in columns],
        )
        created += 1
    print(f"stain_dictionary: {created} created, {len(rows) - created} already present.")


def seed_organ_tissue(cur, rows):
    created, skipped_missing = 0, 0
    for row in rows:
        cur.execute(
            "SELECT organ_id FROM organ_dictionary WHERE organ_name = %s",
            (row["organ_name"],),
        )
        organ = cur.fetchone()
        cur.execute(
            "SELECT tissue_id FROM tissue_dictionary WHERE tissue_name = %s",
            (row["tissue_name"],),
        )
        tissue = cur.fetchone()
        if not organ or not tissue:
            skipped_missing += 1
            continue

        cur.execute(
            "SELECT 1 FROM organ_tissue_dictionary WHERE organ_id = %s AND tissue_id = %s",
            (organ["organ_id"], tissue["tissue_id"]),
        )
        if cur.fetchone():
            continue

        cur.execute(
            """
            INSERT INTO organ_tissue_dictionary
                (organ_id, tissue_id, relationship_type, notes, review_status, confidence)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                organ["organ_id"],
                tissue["tissue_id"],
                row.get("relationship_type"),
                row.get("notes"),
                row.get("review_status"),
                row.get("confidence"),
            ),
        )
        created += 1
    print(
        f"organ_tissue_dictionary: {created} created "
        f"({skipped_missing} skipped - organ/tissue not found by name)."
    )


def main():
    if not os.path.exists(DICTIONARIES_JSON):
        print(f"Seed file not found: {DICTIONARIES_JSON}", file=sys.stderr)
        sys.exit(1)

    with open(DICTIONARIES_JSON, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            seed_simple_dictionary(cur, "organ_dictionary", "organ_name", "organ_id", data["organ"])
            seed_simple_dictionary(cur, "tissue_dictionary", "tissue_name", "tissue_id", data["tissue"])
            seed_simple_dictionary(cur, "species_dictionary", "species_name", "species_id", data["species"])
            seed_stain_dictionary(cur, data["stain"])
            seed_organ_tissue(cur, data["organ_tissue"])
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"Seeding failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
