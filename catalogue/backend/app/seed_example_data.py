#!/usr/bin/env python3
"""Seeds a freshly-created, empty catalogue database with one example admin
user and three example slides (real teaching histology images, non-human
specimens only, checked-in thumbnails), so a fresh clone has something to
log in with and look at.

Safe to re-run - skips anything that already exists by username/filename.

Run inside the backend container, after 0000_initial_schema.sql and the
000N_*.sql migrations have been applied:

    docker exec -it catalogue_backend python3 /app/app/seed_example_data.py
"""

import os
import shutil
import sys

import pymysql
from argon2 import PasswordHasher

EXAMPLE_USERNAME = "admin"
EXAMPLE_PASSWORD = "ChangeMe123!"
EXAMPLE_EMAIL = "admin@example.com"
EXAMPLE_FULL_NAME = "Example Administrator"

THUMBNAIL_DIR = "/srv/thumbnails"
EXAMPLE_DATA_DIR = os.path.join(os.path.dirname(__file__), "example_data")
THUMBNAIL_SIZES = (512, 1024, 2048)

# Three real teaching-histology slides (non-human specimens only), with
# real slide/technical metadata but sanitized share paths. Thumbnail
# source_key points at the checked-in file under example_data/thumbnails/.
EXAMPLE_SLIDES = [
    {
        "source_key": "1",
        "filename": "Slide AD139 Kidney Dog H&E - example.ndpi",
        "archive_relative_path": "Archive/Urinary/Renal/Kidney unannotated/Slide AD139 Kidney Dog H&E - example.ndpi",
        "slide_format": "NDPI",
        "file_size_bytes": 269105756,
        "width_pixels": 51200,
        "height_pixels": 29440,
        "objective_magnifications": "20x",
        "organ": "Kidney",
        "species": "Dog",
        "stain": "H&E",
        "magnification": 20,
        "is_z_stack": 0,
        "z_plane_count": None,
        "technical": {
            "openslide_status": "SUCCESS",
            "openslide_vendor": "hamamatsu",
            "tiffslide_status": "SUCCESS",
            "tiffslide_vendor": "hamamatsu",
            "openslide_mpp_x": 0.455083280240284,
            "openslide_mpp_y": 0.455062571103527,
            "tiffslide_mpp_x": 0.455083280240284,
            "tiffslide_mpp_y": 0.455062571103527,
        },
    },
    {
        "source_key": "2",
        "filename": "Slide 1282 Lung Rabbit H&E - example.ndpi",
        "archive_relative_path": "Archive/Pulmonary/Lung/Lung unannotated/Slide 1282 Lung Rabbit H&E - example.ndpi",
        "slide_format": "NDPI",
        "file_size_bytes": 1046411512,
        "width_pixels": 47104,
        "height_pixels": 39680,
        "objective_magnifications": "20x",
        "organ": "Lung",
        "species": "Rabbit",
        "stain": "H&E",
        "magnification": 20,
        "is_z_stack": 1,
        "z_plane_count": 5,
        "technical": {
            "openslide_status": "SUCCESS",
            "openslide_vendor": "hamamatsu",
            "tiffslide_status": "SUCCESS",
            "tiffslide_vendor": "hamamatsu",
            "openslide_mpp_x": 0.455083280240284,
            "openslide_mpp_y": 0.455062571103527,
            "tiffslide_mpp_x": None,
            "tiffslide_mpp_y": None,
        },
    },
    {
        "source_key": "3",
        "filename": "Slide 722 Sublingual gland Dog H&E - example.ndpi",
        "archive_relative_path": "Archive/Alimentary/Mouth/Salivary glands/Slide 722 Sublingual gland Dog H&E - example.ndpi",
        "slide_format": "NDPI",
        "file_size_bytes": 66509952,
        "width_pixels": 20480,
        "height_pixels": 27392,
        "objective_magnifications": "20x",
        "organ": "Salivary gland",
        "species": "Dog",
        "stain": "H&E",
        "magnification": 20,
        "is_z_stack": 0,
        "z_plane_count": None,
        "technical": {
            "openslide_status": "SUCCESS",
            "openslide_vendor": "hamamatsu",
            "tiffslide_status": "SUCCESS",
            "tiffslide_vendor": "hamamatsu",
            "openslide_mpp_x": 0.455145418961358,
            "openslide_mpp_y": 0.455145418961358,
            "tiffslide_mpp_x": 0.455145418961358,
            "tiffslide_mpp_y": 0.455145418961358,
        },
    },
]


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


def seed_user(cur):
    cur.execute(
        "SELECT user_id FROM users WHERE username = %s",
        (EXAMPLE_USERNAME,),
    )
    if cur.fetchone():
        print(f"User '{EXAMPLE_USERNAME}' already exists - skipping.")
        return

    password_hasher = PasswordHasher()

    cur.execute(
        """
        INSERT INTO users (
            username,
            email,
            full_name,
            role,
            authentication_method,
            account_status,
            password_hash
        )
        VALUES (%s, %s, %s, 'system_admin', 'LOCAL', 'ACTIVE', %s)
        """,
        (
            EXAMPLE_USERNAME,
            EXAMPLE_EMAIL,
            EXAMPLE_FULL_NAME,
            password_hasher.hash(EXAMPLE_PASSWORD),
        ),
    )

    print(f"Created user '{EXAMPLE_USERNAME}' (role: system_admin).")
    print(f"  Login: {EXAMPLE_USERNAME} / {EXAMPLE_PASSWORD}")
    print("  Change this password immediately outside of local testing.")


def seed_slide(cur, slide):
    cur.execute(
        "SELECT slide_id FROM slides WHERE filename = %s",
        (slide["filename"],),
    )
    existing = cur.fetchone()
    if existing:
        print(f"Slide '{slide['filename']}' already exists - skipping.")
        return existing["slide_id"], False

    cur.execute(
        """
        INSERT INTO slides (
            filename,
            physical_path,
            archive_relative_path,
            slide_format,
            file_size_bytes,
            width_pixels,
            height_pixels,
            metadata_status,
            asset_status,
            objective_magnifications
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'MATCHED_METADATA', 'ACTIVE', %s)
        """,
        (
            slide["filename"],
            "/mnt/virtual-microscopy/" + slide["archive_relative_path"],
            slide["archive_relative_path"],
            slide["slide_format"],
            slide["file_size_bytes"],
            slide["width_pixels"],
            slide["height_pixels"],
            slide["objective_magnifications"],
        ),
    )
    slide_id = cur.lastrowid

    cur.execute(
        """
        INSERT INTO slide_metadata (
            slide_id,
            organ,
            species,
            stain,
            magnification,
            description,
            is_z_stack,
            z_plane_count
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            slide_id,
            slide["organ"],
            slide["species"],
            slide["stain"],
            slide["magnification"],
            "Example slide seeded for local testing.",
            slide["is_z_stack"],
            slide["z_plane_count"],
        ),
    )

    t = slide["technical"]
    cur.execute(
        """
        INSERT INTO slide_technical_metadata (
            slide_id,
            openslide_status,
            openslide_vendor,
            tiffslide_status,
            tiffslide_vendor,
            openslide_mpp_x,
            openslide_mpp_y,
            tiffslide_mpp_x,
            tiffslide_mpp_y,
            technical_metadata_source
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'seed_example_data')
        """,
        (
            slide_id,
            t["openslide_status"],
            t["openslide_vendor"],
            t["tiffslide_status"],
            t["tiffslide_vendor"],
            t["openslide_mpp_x"],
            t["openslide_mpp_y"],
            t["tiffslide_mpp_x"],
            t["tiffslide_mpp_y"],
        ),
    )

    print(f"Created example slide '{slide['organ']}/{slide['species']}/{slide['stain']}' (slide_id={slide_id}).")
    return slide_id, True


def seed_thumbnails(slide_id, source_key):
    copied = []
    for size in THUMBNAIL_SIZES:
        dest = os.path.join(THUMBNAIL_DIR, str(size), f"{slide_id}.jpg")
        if os.path.exists(dest):
            continue
        source = os.path.join(EXAMPLE_DATA_DIR, "images", str(size), f"{source_key}.jpg")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(source, dest)
        copied.append(size)

    if copied:
        print(f"Placed thumbnails for slide_id={slide_id} at {copied}.")
    else:
        print(f"Thumbnails for slide_id={slide_id} already exist - skipping.")


def main():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            seed_user(cur)
            created_slides = []
            for slide in EXAMPLE_SLIDES:
                slide_id, created = seed_slide(cur, slide)
                created_slides.append((slide_id, slide["source_key"]))
        conn.commit()
        for slide_id, source_key in created_slides:
            seed_thumbnails(slide_id, source_key)
    except Exception as exc:
        conn.rollback()
        print(f"Seeding failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
