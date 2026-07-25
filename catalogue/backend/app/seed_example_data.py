#!/usr/bin/env python3
"""Seeds a freshly-created, empty catalogue database with one example admin
user and one example slide (with generated placeholder thumbnails), so a
fresh clone has something to log in with and look at.

Safe to re-run - skips anything that already exists by username/filename.

Run inside the backend container, after 0000_initial_schema.sql and the
000N_*.sql migrations have been applied:

    docker exec -it catalogue_backend python3 /app/app/seed_example_data.py
"""

import os
import random
import sys

import pymysql
from argon2 import PasswordHasher
from PIL import Image, ImageDraw

EXAMPLE_USERNAME = "admin"
EXAMPLE_PASSWORD = "ChangeMe123!"
EXAMPLE_EMAIL = "admin@example.com"
EXAMPLE_FULL_NAME = "Example Administrator"

EXAMPLE_SLIDE_FILENAME = "example-slide.ndpi"
THUMBNAIL_SIZES = (512, 1024, 2048)
THUMBNAIL_DIR = "/srv/thumbnails"


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


def generate_example_thumbnail(path, size):
    """Draws a synthetic, generic H&E-style placeholder image - not a real
    slide scan - so example listings and the slide detail page have
    something to show instead of a broken image."""

    rng = random.Random(1234)
    width, height = size, size // 2

    image = Image.new("RGB", (width, height), (238, 219, 231))
    draw = ImageDraw.Draw(image)

    for _ in range(int(width * height / 900)):
        x = rng.randint(0, width)
        y = rng.randint(0, height)
        r = rng.randint(2, max(3, width // 120))
        shade = rng.randint(90, 150)
        draw.ellipse(
            (x - r, y - r, x + r, y + r),
            fill=(shade, 30, shade + 40),
        )

    os.makedirs(os.path.dirname(path), exist_ok=True)
    image.save(path, "JPEG", quality=85)


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


def seed_slide(cur):
    cur.execute(
        "SELECT slide_id FROM slides WHERE filename = %s",
        (EXAMPLE_SLIDE_FILENAME,),
    )
    existing = cur.fetchone()
    if existing:
        print(f"Slide '{EXAMPLE_SLIDE_FILENAME}' already exists - skipping.")
        return existing["slide_id"]

    cur.execute(
        """
        INSERT INTO slides (
            filename,
            physical_path,
            slide_format,
            file_size_bytes,
            width_pixels,
            height_pixels,
            metadata_status,
            asset_status
        )
        VALUES (%s, %s, 'ndpi', 0, 2048, 1024, 'MATCHED_METADATA', 'ACTIVE')
        """,
        (
            EXAMPLE_SLIDE_FILENAME,
            f"example/{EXAMPLE_SLIDE_FILENAME}",
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
            description
        )
        VALUES (%s, 'Kidney', 'Human', 'H&E', %s)
        """,
        (
            slide_id,
            "Example slide seeded for local testing - not a real specimen.",
        ),
    )

    print(f"Created example slide (slide_id={slide_id}).")
    return slide_id


def seed_thumbnails(slide_id):
    created = []
    for size in THUMBNAIL_SIZES:
        path = os.path.join(THUMBNAIL_DIR, str(size), f"{slide_id}.jpg")
        if os.path.exists(path):
            continue
        generate_example_thumbnail(path, size)
        created.append(size)

    if created:
        print(f"Generated placeholder thumbnails for slide_id={slide_id} at {created}.")
    else:
        print(f"Thumbnails for slide_id={slide_id} already exist - skipping.")


def main():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            seed_user(cur)
            slide_id = seed_slide(cur)
        conn.commit()
        seed_thumbnails(slide_id)
    except Exception as exc:
        conn.rollback()
        print(f"Seeding failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
