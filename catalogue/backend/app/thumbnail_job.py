"""Background thumbnail generation triggered from the sysadmin "Import
Batches" web UI (see migrations/0015_add_thumbnail_jobs.sql). No task-queue
infrastructure exists anywhere in this app, and none is being introduced
for this one feature - a plain threading.Thread fits this codebase's
existing plain-FastAPI/pymysql/no-heavy-deps style better than either
FastAPI BackgroundTasks (ties the task to one request/response lifecycle
with less controllable exception handling than the explicit try/except
this module needs anyway, to build the manual-thumbnail-needed list) or a
job-file/external-watcher (a whole new process for no real gain in this
single-container-per-service stack).

Progress is persisted to thumbnail_jobs regardless of dispatch mechanism,
since the polling GET request is a separate HTTP request/thread from the
one that started the job - there's no in-memory object to hand it.

The actual per-slide generation logic (open_slide/crop_background/
generate_for_slide, SIZES/THUMBNAIL_SIZE/DEFAULT_CROP_THRESHOLD) is
deliberately duplicated from catalogue/tools/populate_new_slide_thumbnails.py
rather than imported from it - that script is a standalone host CLI tool
(argparse entry point, not a library), and this module now runs inside
catalogue_backend itself, which is why that container needed a real
filesystem mount to the slide archive and OpenSlide/TiffSlide added to its
image in the first place (it had neither before this feature).
"""

import json
import multiprocessing
import os
import threading

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
THUMBNAILS_ROOT = "/srv/thumbnails"
PER_SLIDE_TIMEOUT_SECONDS = 90

# "spawn", not the Linux default "fork" - forking a multi-threaded process
# (this module runs inside a background thread of a multi-threaded uvicorn
# process) risks inheriting locks held by other threads at fork time and is
# a known source of subtle deadlocks. spawn starts a genuinely fresh
# interpreter per slide instead - slower to start, but the correctness this
# buys is worth it for something that only needs to run once per slide.
_mp_context = multiprocessing.get_context("spawn")


def _db_config():
    """Matches main.py's own get_db_connection() env vars exactly - this
    module needs its own connection function (not a shared import) since it
    runs on a background thread and pymysql connections aren't thread-safe,
    so it can never reuse the request-scoped connection get_db_connection()
    hands out."""
    return {
        "host": os.getenv("DB_HOST", "catalogue_mariadb"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }


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


def generate_for_slide(slide_path, slide_id, threshold=DEFAULT_CROP_THRESHOLD):
    slide = open_slide(slide_path)
    try:
        thumb = slide.get_thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
        thumb = crop_background(thumb, threshold)
        if thumb.mode != "RGB":
            thumb = thumb.convert("RGB")
        for size in SIZES:
            size_dir = os.path.join(THUMBNAILS_ROOT, str(size))
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


def generate_dicom_thumbnail(slide_path, slide_id):
    """DICOM pixel data isn't touched by de-identification (only header
    tags are - see app/dicom_deidentify.py) so it's always safe to read
    directly from physical_path here. Callers must still never invoke this
    for a slide whose dicom_deidentification_mode is NULL - see the guard
    in run_job() - that's what stops a raw, un-scrubbed file from ever
    being read at all, regardless of what this function itself touches.

    OpenSlide/TiffSlide don't apply here (most real-world DICOM teaching
    content is single/multi-frame radiology, not the WSI-pyramid DICOM
    subset OpenSlide 4.x added support for), so this reads pixel data
    directly via pydicom and does its own basic windowing - no vendor
    pyramid/tiling to lean on.
    """
    if pydicom is None or np is None:
        raise RuntimeError("pydicom/numpy unavailable")

    ds = pydicom.dcmread(slide_path)
    arr = ds.pixel_array

    # Multi-frame (or multi-frame-shaped) data - use the middle frame as a
    # representative preview rather than the first, and never try to render
    # every frame into one thumbnail.
    if arr.ndim >= 3:
        frame_count = arr.shape[0]
        arr = arr[frame_count // 2]

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
        # No window hint in the file - fall back to the data's own range
        # (min-max normalization) rather than guessing a modality-specific
        # default.
        lo, hi = float(arr.min()), float(arr.max())
    if hi <= lo:
        hi = lo + 1

    arr = np.clip((arr - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)
    if getattr(ds, "PhotometricInterpretation", "") == "MONOCHROME1":
        arr = 255 - arr  # MONOCHROME1: 0=white - invert so higher values render brighter, like MONOCHROME2

    img = Image.fromarray(arr).convert("RGB")

    for size in SIZES:
        size_dir = os.path.join(THUMBNAILS_ROOT, str(size))
        os.makedirs(size_dir, exist_ok=True)
        sized = img.copy()
        sized.thumbnail((size, size), Image.Resampling.LANCZOS)
        sized.save(
            os.path.join(size_dir, f"{slide_id}.jpg"),
            format="JPEG", quality=90, optimize=True,
        )


def _generate_dicom_worker(slide_path, slide_id, result_queue):
    try:
        generate_dicom_thumbnail(slide_path, slide_id)
        result_queue.put(("ok", None))
    except Exception as exc:
        result_queue.put(("error", str(exc)))


def generate_dicom_thumbnail_with_timeout(slide_path, slide_id, timeout_seconds=PER_SLIDE_TIMEOUT_SECONDS):
    """Same subprocess-timeout protection as generate_for_slide_with_timeout
    - see that function's docstring for why this can't just be an in-process
    timeout."""
    result_queue = _mp_context.Queue()
    process = _mp_context.Process(
        target=_generate_dicom_worker, args=(slide_path, slide_id, result_queue)
    )
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
        raise RuntimeError(f"Timed out after {timeout_seconds}s (file may be stuck/corrupt)")

    if result_queue.empty():
        raise RuntimeError(
            f"Generation process exited unexpectedly (exit code {process.exitcode}) with no result"
        )

    status, error = result_queue.get()
    if status == "error":
        raise RuntimeError(error)


def _generate_worker(slide_path, slide_id, threshold, result_queue):
    """Runs in a fresh spawned process - must be a module-level function
    (not a closure/lambda) since spawn re-imports this module rather than
    forking, and needs a picklable target to hand off to."""
    try:
        generate_for_slide(slide_path, slide_id, threshold)
        result_queue.put(("ok", None))
    except Exception as exc:
        result_queue.put(("error", str(exc)))


def generate_for_slide_with_timeout(slide_path, slide_id, threshold=DEFAULT_CROP_THRESHOLD, timeout_seconds=PER_SLIDE_TIMEOUT_SECONDS):
    """Isolates one slide's generation in its own subprocess with a hard
    timeout - a stuck OpenSlide/TiffSlide read inside a long-running
    background thread can hang indefinitely with near-zero CPU, invisible
    to any in-process Python-level timeout (the GIL/thread model can't
    interrupt a blocked native call) and leaving no trace in MariaDB's own
    process list either - only a real OS-level process kill actually
    recovers from it."""
    result_queue = _mp_context.Queue()
    process = _mp_context.Process(
        target=_generate_worker, args=(slide_path, slide_id, threshold, result_queue)
    )
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
        raise RuntimeError(
            f"Timed out after {timeout_seconds}s (file may be stuck/corrupt)"
        )

    if result_queue.empty():
        raise RuntimeError(
            f"Generation process exited unexpectedly (exit code {process.exitcode}) with no result"
        )

    status, error = result_queue.get()
    if status == "error":
        raise RuntimeError(error)


def start_job(slide_ids, batch_id, admin_user):
    """Rejects (raises ValueError -> caller returns 409) if a job is
    already queued/running - one at a time, deliberately simple given
    typical batch sizes (tens to low hundreds of slides). Returns the new
    job_id immediately; the actual work happens on a background thread."""
    conn = pymysql.connect(**_db_config())
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT job_id FROM thumbnail_jobs WHERE status IN ('queued', 'running') LIMIT 1"
            )
            if cur.fetchone():
                raise ValueError("A thumbnail job is already running - wait for it to finish first")

            cur.execute(
                "INSERT INTO thumbnail_jobs (batch_id, total_slides, triggered_by_user_id, "
                "triggered_by_username) VALUES (%s, %s, %s, %s)",
                (batch_id, len(slide_ids), admin_user.get("user_id"), admin_user.get("username")),
            )
            job_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    thread = threading.Thread(target=run_job, args=(job_id, slide_ids), daemon=True)
    thread.start()
    return job_id


def run_job(job_id, slide_ids):
    """Runs on the background thread with its OWN pymysql connection -
    pymysql connections are not thread-safe, never share the request's
    connection with a background thread. Commits progress after EACH slide
    so a concurrent polling GET (on a different connection/thread) reads
    live state, not just the final result."""
    conn = pymysql.connect(**_db_config())
    manual_needed = []
    succeeded = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE thumbnail_jobs SET status='running', started_at=NOW() WHERE job_id=%s",
                (job_id,),
            )
        conn.commit()

        for processed, slide_id in enumerate(slide_ids, start=1):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT filename, physical_path, slide_format, "
                    "dicom_deidentification_mode FROM slides WHERE slide_id=%s",
                    (slide_id,),
                )
                slide = cur.fetchone()

            if slide is None:
                manual_needed.append({
                    "slide_id": slide_id, "filename": None, "physical_path": None,
                    "error": "slide_id not found",
                })
            elif slide["slide_format"] == "DICOM" and not slide["dicom_deidentification_mode"]:
                # Safety net: never read a DICOM file whose source hasn't
                # been through a de-identification pass, even just to
                # generate a thumbnail - de-identification only touches
                # header tags, but the file itself may also carry
                # burned-in PHI in the pixel data this job would otherwise
                # render straight into a public thumbnail.
                manual_needed.append({
                    "slide_id": slide_id,
                    "filename": slide["filename"],
                    "physical_path": slide["physical_path"],
                    "error": "DICOM slide has not been de-identified yet - see "
                    "sysadmin > System Settings for the site's default "
                    "de-identification mode before a thumbnail can be generated.",
                })
            else:
                try:
                    if slide["slide_format"] == "DICOM":
                        generate_dicom_thumbnail_with_timeout(slide["physical_path"], slide_id)
                    else:
                        generate_for_slide_with_timeout(slide["physical_path"], slide_id)
                    succeeded += 1
                except Exception as exc:
                    manual_needed.append({
                        "slide_id": slide_id,
                        "filename": slide["filename"],
                        "physical_path": slide["physical_path"],
                        "error": str(exc),
                    })

            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE thumbnail_jobs SET processed_slides=%s, succeeded_slides=%s, "
                    "manual_needed_detail_json=%s WHERE job_id=%s",
                    (processed, succeeded, json.dumps(manual_needed), job_id),
                )
            conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE thumbnail_jobs SET status='completed', finished_at=NOW() WHERE job_id=%s",
                (job_id,),
            )
        conn.commit()
    except Exception as exc:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE thumbnail_jobs SET status='failed', error_message=%s, finished_at=NOW() "
                "WHERE job_id=%s",
                (str(exc), job_id),
            )
        conn.commit()
    finally:
        conn.close()
