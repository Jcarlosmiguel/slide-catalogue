#!/usr/bin/env python3

from pathlib import Path
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
from datetime import datetime
import shutil

MANUAL_DIR = Path("/srv/manual_thumbnails")
THUMB_DIR = Path("/srv/thumbnails")
BACKUP_ROOT = Path("/srv/thumbnail_backups")

LOG_FILE = BACKUP_ROOT / "thumbnail_sync.log"

SIZES = [2048, 1024, 512]


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} {message}"
    print(line)

    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    with open(LOG_FILE, "a") as fh:
        fh.write(line + "\n")


def backup_file(src, backup_dir):
    if src.exists():
        backup_dir.mkdir(parents=True, exist_ok=True)

        backup_name = f"{src.parent.name}_{src.name}"

        shutil.copy2(
            src,
            backup_dir / backup_name
        )

def create_thumbnail(source_png, target_jpg, max_size):
    with Image.open(source_png) as img:

        if img.mode not in ("RGB",):
            img = img.convert("RGB")

        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        img.save(
            target_jpg,
            format="JPEG",
            quality=90,
            optimize=True
        )


def process_png(png_file):
    """Returns {"slide_id": str, "status": "CREATED"|"OK"|"ERROR", "error": str|None} -
    the status/error fields let callers (e.g. the sysadmin-triggered API
    endpoint) report exactly what happened per file, on top of the existing
    print/log-file trail this function already writes."""

    slide_id = png_file.stem

    if not slide_id.isdigit():
        message = f"invalid filename {png_file.name}"
        log(f"ERROR {message}")
        return {"slide_id": png_file.stem, "status": "ERROR", "error": message}

    master_jpg = THUMB_DIR / "2048" / f"{slide_id}.jpg"
    is_new = not master_jpg.exists()

    today = datetime.now().strftime("%Y-%m-%d")
    backup_dir = BACKUP_ROOT / today / slide_id

    try:

        if not is_new:
            for size in SIZES:
                source = THUMB_DIR / str(size) / f"{slide_id}.jpg"
                backup_file(source, backup_dir)

        for size in SIZES:
            target = THUMB_DIR / str(size) / f"{slide_id}.jpg"
            target.parent.mkdir(parents=True, exist_ok=True)
            create_thumbnail(png_file, target, size)

        png_file.unlink()

        status = "CREATED" if is_new else "OK"
        log(f"{status} {slide_id}")
        return {"slide_id": slide_id, "status": status, "error": None}

    except Exception as exc:
        log(f"ERROR {slide_id} {exc}")
        return {"slide_id": slide_id, "status": "ERROR", "error": str(exc)}


def sync():
    """Processes every pending PNG in MANUAL_DIR and returns the list of
    per-file results (see process_png) - the shared entry point for both
    the CLI (main(), below) and the sysadmin-triggered API endpoint."""

    if not MANUAL_DIR.exists():
        log(f"ERROR missing directory {MANUAL_DIR}")
        return []

    pngs = sorted(MANUAL_DIR.glob("*.png"))

    if not pngs:
        log("INFO no PNG files found")
        return []

    return [process_png(png) for png in pngs]


def main():
    sync()


if __name__ == "__main__":
    main()
