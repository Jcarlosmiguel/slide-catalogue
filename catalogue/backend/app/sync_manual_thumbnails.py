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

    slide_id = png_file.stem

    if not slide_id.isdigit():
        log(f"ERROR invalid filename {png_file.name}")
        return

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

        log(f"{'CREATED' if is_new else 'OK'} {slide_id}")

    except Exception as exc:
        log(f"ERROR {slide_id} {exc}")

def main():

    if not MANUAL_DIR.exists():
        log(f"ERROR missing directory {MANUAL_DIR}")
        return

    pngs = sorted(MANUAL_DIR.glob("*.png"))

    if not pngs:
        log("INFO no PNG files found")
        return

    for png in pngs:
        process_png(png)

if __name__ == "__main__":
    main()
