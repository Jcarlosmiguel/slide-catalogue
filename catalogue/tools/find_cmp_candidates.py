#!/usr/bin/env python3
"""Read-only candidate finder for comparison (CMP) slides that haven't been
curated yet - see docs/database.md's stain_dictionary section for what CMP
means and why it can never be fully automated.

Scans every slide's filename for the two lettering/numbering conventions
already used by the real, expert-curated stain_dictionary entries (e.g.
"a) H&E b) PAS", "1.H&E.2.PAS" - patterns derived directly from real
curated examples, not a generic "contains two stain names" guess), and
reports slides matching one of those conventions whose current stain value
doesn't already match a stain_dictionary entry with
stain_family = 'Comparison slide'.

This is a STARTING POINT for finding slides worth a human look, not a
detector - confirmed against real data that some genuine comparison slides
(e.g. "Slide 259 Duodenum Human HE PAS OG") have no lettering/numbering
marker in the filename at all, so this script will never find every real
case, only ones that happen to follow the two conventions above. Report
only - never writes anything.

Usage:
  python3 find_cmp_candidates.py --db-host ... --db-user ... --db-password ... --db-database ...
"""

import argparse
import re
import sys

import pymysql

# "a) <text> b) <text>" - spacing/punctuation varies in real filenames
# (a)HE b)Mucin, a) HE b) Halmi, a)HE, b)Mucin, ...), so this is loose on
# whitespace/comma but anchored on the "a)" ... "b)" lettering itself.
LETTER_PATTERN = re.compile(r"a\)\s*[^()]*?b\s*\)", re.IGNORECASE)

# "1.<text>.2.<text>" - e.g. "1.H&E.2.PAS", "1. H&E. 2. Masson". No \b
# before the "1" deliberately - confirmed against a real filename
# ("...Human1.H&E.2.PAS...") that the "1" is sometimes glued directly to
# a preceding word with no separator, which \b would have missed.
NUMBER_PATTERN = re.compile(r"1\s*\.[^.]*\.\s*2\s*\.", re.IGNORECASE)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Find slides whose filename matches the curated "
        "comparison-slide lettering/numbering convention but aren't "
        "flagged CMP yet - report only, no writes."
    )
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-port", type=int, default=3306)
    parser.add_argument("--db-user", required=True)
    parser.add_argument("--db-password", required=True)
    parser.add_argument("--db-database", required=True)
    args = parser.parse_args(argv)

    conn = pymysql.connect(
        host=args.db_host, port=args.db_port, user=args.db_user,
        password=args.db_password, database=args.db_database,
        cursorclass=pymysql.cursors.DictCursor,
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.slide_id, s.filename, sm.stain
            FROM slides s
            JOIN slide_metadata sm ON sm.slide_id = s.slide_id
            LEFT JOIN stain_dictionary sd ON sd.original_stain = sm.stain
            WHERE s.asset_status = 'ACTIVE'
              AND (sd.stain_family IS NULL OR sd.stain_family != 'Comparison slide')
            ORDER BY s.slide_id
            """
        )
        rows = cur.fetchall()
    conn.close()

    candidates = [
        row for row in rows
        if LETTER_PATTERN.search(row["filename"]) or NUMBER_PATTERN.search(row["filename"])
    ]

    print(f"{len(rows)} active slide(s) not currently matching a Comparison "
          f"slide stain_dictionary entry.")
    print(f"{len(candidates)} of those match the a)/b) or 1./2. filename "
          f"convention - worth a look, in no way exhaustive:\n")

    for row in candidates:
        print(f"  slide_id {row['slide_id']}: {row['filename']}")
        print(f"    current stain: {row['stain'] or '(none)'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
