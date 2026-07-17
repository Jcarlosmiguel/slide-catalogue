#!/usr/bin/env python3

import os
import sys
from PIL import ImageChops

try:
    import openslide
except Exception:
    openslide = None

try:
    from tiffslide import TiffSlide
except Exception:
    TiffSlide = None


SUPPORTED_EXTENSIONS = (
    ".ndpi",
    ".scn",
    ".svs",
    ".mrxs",
    ".vms",
    ".vmu",
    ".tif",
    ".tiff"
)

THUMBNAIL_SIZE = 4096


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

    raise RuntimeError(
        f"Unable to open slide: {slide_path}"
    )

def crop_background(
    img,
    threshold
):

    gray = img.convert("L")

    mask = gray.point(
        lambda p: 255 if p < threshold else 0
    )

    bbox = mask.getbbox()

    if bbox:
        return img.crop(bbox)

    return img

def generate_thumbnail(
    slide_path,
    output_folder,
    threshold
):

    slide_name = os.path.splitext(
        os.path.basename(slide_path)
    )[0]

    output_file = os.path.join(
        output_folder,
        f"{slide_name}.png"
    )

    if os.path.exists(output_file):
        print(f"SKIP: {output_file}")
        return

    slide = open_slide(slide_path)

    try:

        thumb = slide.get_thumbnail(
            (THUMBNAIL_SIZE, THUMBNAIL_SIZE)
        )

        thumb = crop_background(
            thumb,
            threshold
        )

        thumb.save(
            output_file,
            format="PNG"
        )

        print(
            f"OK: {output_file}"
        )

    finally:

        try:
            slide.close()
        except Exception:
            pass

def main():

    if len(sys.argv) < 3:

        print(
            "\nUsage:\n"
            "generate_2048_png_thumbnails.py "
            "<slide_folder> "
            "<output_folder> "
            "[--threshold N]\n"
        )

        sys.exit(1)

    slide_folder = sys.argv[1]
    output_folder = sys.argv[2]

    threshold = 245

    if len(sys.argv) >= 5:

        if sys.argv[3] == "--threshold":

            threshold = int(
                sys.argv[4]
            )

    print(
        f"Cropping threshold: {threshold}"
    )

    os.makedirs(
        output_folder,
        exist_ok=True
    )

    total = 0
    success = 0

    for root, _, files in os.walk(slide_folder):

        for filename in files:

            if not filename.lower().endswith(
                SUPPORTED_EXTENSIONS
            ):
                continue

            total += 1

            slide_path = os.path.join(
                root,
                filename
            )

            try:

                generate_thumbnail(
                    slide_path,
                    output_folder,
                    threshold
                )

                success += 1

            except Exception as exc:

                print(
                    f"ERROR: {slide_path}"
                )

                print(
                    f"       {exc}"
                )

    print(
        f"\nFinished: "
        f"{success}/{total} slides processed.\n"
    )


if __name__ == "__main__":
    main()
