#!/usr/bin/env python3
"""Generates thumbnails directly for slides in the catalogue database that
don't have one yet.

Complements the manual workflow in docs/thumbnail-maintenance.md
(generate_2048_png_thumbnails.py + sync_manual_thumbnails.py) - that pair is
built for *replacing* an existing thumbnail (it backs one up before writing
the new one), not for creating a first one. This script is for slides that
already have a real slide_id in the database but nothing under thumbnails/
yet - typically a batch just imported via a bulk SQL import.

Safe to re-run: any slide with an existing thumbnails/2048/{slide_id}.jpg is
skipped. Uses the same OpenSlide-first/TiffSlide-fallback + whitespace-crop
approach as generate_2048_png_thumbnails.py, so thumbnails look consistent
regardless of which tool produced them.

Slides where automated generation fails (commonly multi-scene/multiview
files, where OpenSlide can't reliably choose which image represents the
slide) are written to a report instead of silently skipped - open each one
in QuPath, export a thumbnail PNG, save it as manual_thumbnails/{slide_id}.png,
then run sync_manual_thumbnails.py to pick it up.
"""

import argparse
import os
import sys

import pymysql
from PIL import Image

try:
    import openslide
except Exception:
    openslide = None

try:
    from tiffslide import TiffSlide
except Exception:
    TiffSlide = None

try:
    import pydicom
    import numpy as np
except Exception:
    pydicom = None
    np = None

SIZES = (2048, 1024, 512)
THUMBNAIL_SIZE = 4096
DEFAULT_CROP_THRESHOLD = 245


def open_slide(slide_path):
    if openslide is not None:
        try:
            return openslide.OpenSlide(slide_path)
        except Exception:
            pass
    if TiffSlide is not None:
        try:
            return TiffSlide(slide_path)
        except Exception:
            pass
    raise RuntimeError(f"Unable to open slide: {slide_path}")


def crop_background(img, threshold):
    gray = img.convert("L")
    mask = gray.point(lambda p: 255 if p < threshold else 0)
    bbox = mask.getbbox()
    return img.crop(bbox) if bbox else img


def generate_for_slide(slide_path, thumbnails_root, slide_id, threshold):
    slide = open_slide(slide_path)
    try:
        thumb = slide.get_thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
        thumb = crop_background(thumb, threshold)
        if thumb.mode != "RGB":
            thumb = thumb.convert("RGB")
        for size in SIZES:
            size_dir = os.path.join(thumbnails_root, str(size))
            os.makedirs(size_dir, exist_ok=True)
            sized = thumb.copy()
            sized.thumbnail((size, size), Image.Resampling.LANCZOS)
            sized.save(
                os.path.join(size_dir, f"{slide_id}.jpg"),
                format="JPEG", quality=90, optimize=True,
            )
    finally:
        try:
            slide.close()
        except Exception:
            pass


def generate_dicom_thumbnail(slide_path, thumbnails_root, slide_id):
    """DICOM pixel data isn't touched by de-identification (only header
    tags are - see app/dicom_deidentify.py in the backend), so it's safe to
    read directly from physical_path here. Callers must never call this for
    a slide whose dicom_deidentification_mode is NULL - see main()'s own
    filtering - that's what stops a raw, un-scrubbed file being read at
    all. Mirrors app/thumbnail_job.py's generate_dicom_thumbnail exactly
    (see that module's own docstring for why OpenSlide/TiffSlide don't
    apply to most real-world DICOM content)."""
    if pydicom is None or np is None:
        raise RuntimeError("pydicom/numpy unavailable")

    ds = pydicom.dcmread(slide_path)
    arr = ds.pixel_array
    if arr.ndim >= 3:
        arr = arr[arr.shape[0] // 2]

    arr = arr.astype(np.float64)
    slope = float(getattr(ds, "RescaleSlope", 1) or 1)
    intercept = float(getattr(ds, "RescaleIntercept", 0) or 0)
    arr = arr * slope + intercept

    center = getattr(ds, "WindowCenter", None)
    width = getattr(ds, "WindowWidth", None)
    if center is not None and width is not None:
        center = float(center[0] if hasattr(center, "__iter__") and not isinstance(center, str) else center)
        width = float(width[0] if hasattr(width, "__iter__") and not isinstance(width, str) else width)
        lo, hi = center - width / 2, center + width / 2
    else:
        lo, hi = float(arr.min()), float(arr.max())
    if hi <= lo:
        hi = lo + 1

    arr = np.clip((arr - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)
    if getattr(ds, "PhotometricInterpretation", "") == "MONOCHROME1":
        arr = 255 - arr

    img = Image.fromarray(arr).convert("RGB")
    for size in SIZES:
        size_dir = os.path.join(thumbnails_root, str(size))
        os.makedirs(size_dir, exist_ok=True)
        sized = img.copy()
        sized.thumbnail((size, size), Image.Resampling.LANCZOS)
        sized.save(
            os.path.join(size_dir, f"{slide_id}.jpg"),
            format="JPEG", quality=90, optimize=True,
        )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate thumbnails for catalogue slides that don't have one yet."
    )
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-port", type=int, default=3306)
    parser.add_argument("--db-user", required=True)
    parser.add_argument("--db-password", required=True)
    parser.add_argument("--db-database", required=True)
    parser.add_argument(
        "--thumbnails-root", required=True,
        help="Path to the catalogue's thumbnails/ directory (contains 2048/1024/512 subfolders)",
    )
    parser.add_argument(
        "--threshold", type=int, default=DEFAULT_CROP_THRESHOLD,
        help=f"Whitespace-crop aggressiveness, same scale as "
        f"generate_2048_png_thumbnails.py (default: {DEFAULT_CROP_THRESHOLD})",
    )
    parser.add_argument(
        "--failed-report", default="failed_thumbnails.txt",
        help="Where to write the list of slides needing manual QuPath thumbnail creation",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Only report how many slides are missing a thumbnail - generate nothing",
    )
    args = parser.parse_args(argv)

    conn = pymysql.connect(
        host=args.db_host, port=args.db_port, user=args.db_user,
        password=args.db_password, database=args.db_database,
        cursorclass=pymysql.cursors.DictCursor,
    )
    with conn.cursor() as cur:
        cur.execute(
            "SELECT slide_id, filename, physical_path, slide_format, "
            "dicom_deidentification_mode FROM slides "
            "WHERE asset_status = 'ACTIVE' ORDER BY slide_id"
        )
        slides = cur.fetchall()
    conn.close()

    blocked_dicom = [
        s for s in slides
        if s["slide_format"] == "DICOM" and not s["dicom_deidentification_mode"]
    ]
    if blocked_dicom:
        print(
            f"{len(blocked_dicom)} DICOM slide(s) have not been de-identified yet "
            "- skipping these entirely (never reading the raw file, even for a "
            "thumbnail) until a de-identification pass has run. See the "
            "sysadmin System Settings page for the site's default mode."
        )
    slides = [s for s in slides if s not in blocked_dicom]

    print(f"{len(slides)} ACTIVE slide(s) in the catalogue.")

    to_process = [
        s for s in slides
        if not os.path.exists(os.path.join(args.thumbnails_root, "2048", f"{s['slide_id']}.jpg"))
    ]
    print(f"{len(to_process)} slide(s) missing a thumbnail.\n")

    if args.dry_run:
        for s in to_process:
            print(f"  slide_id {s['slide_id']}: {s['filename']}")
        return 0

    if not to_process:
        return 0

    failed = []
    for idx, slide in enumerate(to_process, start=1):
        slide_id, filename, physical_path = slide["slide_id"], slide["filename"], slide["physical_path"]
        try:
            if slide["slide_format"] == "DICOM":
                generate_dicom_thumbnail(physical_path, args.thumbnails_root, slide_id)
            else:
                generate_for_slide(physical_path, args.thumbnails_root, slide_id, args.threshold)
            print(f"  [{idx}/{len(to_process)}] slide_id {slide_id} ({filename}): OK")
        except Exception as exc:
            print(f"  [{idx}/{len(to_process)}] slide_id {slide_id} ({filename}): FAILED - {exc}")
            failed.append((slide_id, filename, physical_path, str(exc)))

    if failed:
        with open(args.failed_report, "w", encoding="utf-8") as fh:
            fh.write(
                f"{len(failed)} slide(s) need manual thumbnail creation (commonly "
                "multi-scene/multiview files where OpenSlide can't reliably pick "
                "the right image to thumbnail).\n\n"
                "For each: open in QuPath, export a thumbnail PNG, save it as "
                "manual_thumbnails/<slide_id>.png, then run sync_manual_thumbnails.py.\n\n"
            )
            for slide_id, filename, physical_path, error in failed:
                fh.write(f"slide_id {slide_id}: {filename}\n  path: {physical_path}\n  error: {error}\n\n")
        print(f"\n{len(failed)} slide(s) failed automated generation - see {args.failed_report}")
    else:
        print("\nAll slides processed successfully.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
