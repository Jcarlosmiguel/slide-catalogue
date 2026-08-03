#!/usr/bin/env python3
"""Generates one OME-XML file per slide with stored annotations, directly
from the catalogue database - no QuPath round-trip required. Each file is
importable straight into OMERO via omero-roi-importer
(https://github.com/Jcarlosmiguel/omero-roi-importer).

Complements the "Download annotations (OME-XML)" button on a slide's own
page and the sysadmin-only bulk zip endpoint
(/api/admin/slides/annotations-ome-xml-bulk) - this script is for an
offline/archival run against the database directly, without going through
the web app at all.
"""

import argparse
import os
import sys

import pymysql

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "app"))
from annotation_ome_xml import (  # noqa: E402
    build_ome_xml,
    parse_arrow_style,
    parse_color,
    slugify_filename_hint,
    arrow_style_filename_label,
)

_ANNOTATION_COLUMNS = """
    annotation_id,
    annotation_type,
    rect_x,
    rect_y,
    rect_w,
    rect_h,
    arrow_start_x,
    arrow_start_y,
    arrow_end_x,
    arrow_end_y,
    zoom,
    title,
    description,
    drawing,
    invisible
"""


def output_filename(slide_id, filename, arrow_style, has_arrow):
    name_hint = slugify_filename_hint(filename)
    parts = [f"slide_{slide_id}"]
    if name_hint:
        parts.append(name_hint)
    if has_arrow:
        parts.append(arrow_style_filename_label(arrow_style))
    parts.append("annotations")
    return "_".join(parts) + ".ome.xml"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate an OME-XML annotations file for every slide with stored annotations."
    )
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-port", type=int, default=3306)
    parser.add_argument("--db-user", required=True)
    parser.add_argument("--db-password", required=True)
    parser.add_argument("--db-database", required=True)
    parser.add_argument("--output-dir", required=True, help="Directory to write the .ome.xml files into")
    parser.add_argument("--color", default="00FF00", help="Annotation colour as a hex triplet (default: bright green)")
    parser.add_argument(
        "--arrow-style", default="<", choices=["<", ">", "<>"],
        help="Arrowhead placement for 'arrow'-type annotations (default: '<', head at start)",
    )
    parser.add_argument(
        "--no-zoom", action="store_true",
        help="Don't multiply rect/point coordinates by each annotation's own 'zoom' field",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Only report which slides would be processed - generate nothing",
    )
    args = parser.parse_args(argv)

    color = parse_color(args.color)
    arrow_style = parse_arrow_style(args.arrow_style)
    apply_zoom = not args.no_zoom

    conn = pymysql.connect(
        host=args.db_host, port=args.db_port, user=args.db_user,
        password=args.db_password, database=args.db_database,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT s.slide_id, s.filename
                FROM slides s
                JOIN slide_annotations sa ON sa.slide_id = s.slide_id
                WHERE sa.flagged_incorrect = 0
                ORDER BY s.slide_id
                """
            )
            slides = cur.fetchall()

        print(f"{len(slides)} slide(s) with stored annotations.\n")

        if args.dry_run:
            for slide in slides:
                print(f"  slide_id {slide['slide_id']}: {slide['filename']}")
            return 0

        os.makedirs(args.output_dir, exist_ok=True)

        failed = []
        for idx, slide_row in enumerate(slides, start=1):
            slide_id, filename = slide_row["slide_id"], slide_row["filename"]
            try:
                with conn.cursor() as ann_cur:
                    ann_cur.execute(
                        f"""
                        SELECT {_ANNOTATION_COLUMNS}
                        FROM slide_annotations
                        WHERE slide_id = %s AND flagged_incorrect = 0
                        ORDER BY annotation_id
                        """,
                        (slide_id,),
                    )
                    annotations = ann_cur.fetchall()

                if not annotations:
                    continue

                xml, _marked_invisible, _skipped = build_ome_xml(
                    slide_row, annotations, apply_zoom=apply_zoom,
                    color=color, arrow_style=arrow_style,
                )
                has_arrow = any((a.get("annotation_type") or "").lower() == "arrow" for a in annotations)
                out_name = output_filename(slide_id, filename, arrow_style, has_arrow)
                with open(os.path.join(args.output_dir, out_name), "w", encoding="utf-8") as fh:
                    fh.write(xml)
                print(f"  [{idx}/{len(slides)}] slide_id {slide_id} ({filename}): OK -> {out_name}")
            except Exception as exc:
                print(f"  [{idx}/{len(slides)}] slide_id {slide_id} ({filename}): FAILED - {exc}")
                failed.append((slide_id, filename, str(exc)))
    finally:
        conn.close()

    if failed:
        print(f"\n{len(failed)} slide(s) failed:")
        for slide_id, filename, error in failed:
            print(f"  slide_id {slide_id} ({filename}): {error}")
    else:
        print("\nAll slides processed successfully.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
