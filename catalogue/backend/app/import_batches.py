"""Backing logic for the sysadmin "Import Batches" web workflow - uploading
a completed crawler-tool run (.sql + .report.txt + .run.log matching the
format documented in catalogue/docs/import-batches.md), resolving whatever
the crawl left ambiguous, and committing the whole thing as one
transactional import with fresh slide_ids. See
migrations/0015_add_import_batches.sql for the schema this backs.

Ambiguous files (a filename that matched more than one candidate location)
are never in the uploaded .sql at all - a well-behaved crawler tool
deliberately excludes them, leaving resolution to a human. This module is
that human step's backend: parse_report() recovers the ambiguous list from
the uploaded report (deduplicated by filename - see below), find_disk_matches()
locates every real file on disk that could be this ambiguous filename
(migrations/0016_add_ambiguous_file_matches.sql - one row per real file,
resolved independently, since 2-3 real files sharing a name can be true
duplicates or a genuine collision), and build_ambiguous_resolution_sql()
turns a chosen resolution into the same shape of INSERT statements a
crawler tool's own SQL writer would have produced had it not been
ambiguous.
"""

import hashlib
import os
import re

from app.admin_sql import BLOCKED_KEYWORDS, _leading_keyword, _split_statements, _strip_leading_comments
from app import thumbnail_job

try:
    import tifffile
except Exception:
    tifffile = None

# Fixed container-internal path - the host's real archive share (whatever
# SHARE_ROOT_LINUX points to for this deployment) is mounted here read-only
# by compose.yaml, same /srv/* convention as every other volume this
# container uses (manual_thumbnails, thumbnails, backups, import_batches).
ARCHIVE_ROOT = "/srv/archive"

# START/COMMIT are allowed to appear (a crawler tool's own output may wrap
# everything in START TRANSACTION;/COMMIT;) but are stripped before
# execution in commit_batch() below, never actually run - this endpoint's
# transaction boundary is the connection's own commit()/rollback(), same
# as every other mutating endpoint in this codebase. Executing the
# uploaded file's own COMMIT verbatim would prematurely persist the base
# import before the ambiguous-resolution statements appended after it run,
# breaking the atomicity the whole point of this design is to guarantee.
_ALLOWED_BATCH_KEYWORDS = {"SET", "INSERT", "START", "COMMIT"}
_TRANSACTION_CONTROL_KEYWORDS = {"START", "COMMIT"}

_SUMMARY_LINE_PATTERNS = {
    "real_files_crawled": re.compile(r"^Real files crawled:\s*(\d+)"),
    "linked": re.compile(r"^\s*linked:\s*(\d+)"),
    "share_only": re.compile(r"^\s*share-only \(no external record\):\s*(\d+)"),
    "ambiguous": re.compile(r"^\s*ambiguous \(matched >1 folder\):\s*(\d+)"),
    "orphans": re.compile(r"^external records with no matching real file \(orphans\):\s*(\d+)"),
}
_ANNOTATIONS_LINE = re.compile(
    r"^Region annotations imported:\s*(\d+)\s*across\s*(\d+)\s*slide"
)
_AMBIGUOUS_SECTION_HEADER = "Ambiguous filenames (not auto-resolved, review manually):"
_AMBIGUOUS_LINE = re.compile(r"^\s{2}(.+?) -> (.+)$")
_CRAWLED_FOLDER_LINE = re.compile(r"^Crawled folder:\s*(.+)$")


def parse_report(report_text):
    """Extracts summary counts, the deduplicated ambiguous-filenames list,
    and the archive root name from a crawler tool's .report.txt. Line-prefix
    based, matching the format documented in catalogue/docs/import-batches.md -
    if a producing tool's format ever changes, this needs updating alongside it.

    The ambiguous section is deduplicated by filename: the same filename
    can appear multiple times in the raw report (once per real physical
    file sharing that name), each occurrence listing the same candidate
    folders. Keeping them as separate rows would produce identical-looking,
    unresolvable UI entries with no way to tell which was which -
    find_disk_matches() is what actually distinguishes the real files
    apart, so this only needs one row per distinct name, with
    candidate_folders merged as a set union across every occurrence.
    """
    # real_files_crawled defaults to 0 since any real tool should report
    # it - its absence more likely means a genuine parsing mismatch worth
    # surfacing as zero. The rest are deliberately left OUT unless a
    # matching line is actually found, rather than defaulted to 0 - a tool
    # like slide-crawler that does no external reconciliation at all will
    # never produce "linked"/"ambiguous"/"orphans" lines, and defaulting
    # those to 0 would misleadingly read as "reconciled, found nothing"
    # instead of "this tool doesn't report this". The frontend shows
    # "not reported by this tool" for whichever keys are absent here.
    summary = {"real_files_crawled": 0}
    ambiguous_by_filename = {}
    archive_root_name = None

    lines = report_text.splitlines()
    in_ambiguous_section = False

    for line in lines:
        if line.strip() == _AMBIGUOUS_SECTION_HEADER:
            in_ambiguous_section = True
            continue

        if in_ambiguous_section:
            if not line.strip():
                in_ambiguous_section = False
                continue
            match = _AMBIGUOUS_LINE.match(line)
            if match:
                filename = match.group(1).strip()
                folders = {f.strip() for f in match.group(2).split(",")}
                ambiguous_by_filename.setdefault(filename, set()).update(folders)
            continue

        crawled_match = _CRAWLED_FOLDER_LINE.match(line)
        if crawled_match:
            archive_root_name = os.path.basename(crawled_match.group(1).strip().rstrip("/\\"))
            continue

        for key, pattern in _SUMMARY_LINE_PATTERNS.items():
            match = pattern.match(line)
            if match:
                summary[key] = int(match.group(1))
                break

        ann_match = _ANNOTATIONS_LINE.match(line)
        if ann_match:
            summary["annotations_imported"] = int(ann_match.group(1))
            summary["annotations_across_slides"] = int(ann_match.group(2))

    ambiguous = [
        {"filename": filename, "candidate_folders": sorted(folders)}
        for filename, folders in ambiguous_by_filename.items()
    ]

    return {"summary": summary, "ambiguous": ambiguous, "archive_root_name": archive_root_name}


def validate_batch_sql(sql_text):
    """Splits the uploaded .sql into individual statements (reusing
    admin_sql.py's own quote/comment-aware splitter rather than
    reimplementing it) and rejects anything that shouldn't be in an
    unattended import: DROP/TRUNCATE (same as the interactive SQL console)
    plus anything whose leading keyword isn't SET or INSERT - stricter than
    the console, since nobody is watching this run statement-by-statement.
    Raises ValueError with a user-facing message on any violation. Returns
    the statement list on success."""
    if not sql_text or not sql_text.strip():
        raise ValueError("Uploaded .sql file is empty")

    statements = _split_statements(sql_text)
    if not statements:
        raise ValueError("No SQL statements found in the uploaded file")

    for statement in statements:
        keyword = _leading_keyword(statement)
        if not keyword:
            raise ValueError(f"Could not determine statement type for: {statement[:80]}...")
        if keyword in BLOCKED_KEYWORDS:
            raise ValueError(f"{keyword} is not permitted in an import batch")
        if keyword not in _ALLOWED_BATCH_KEYWORDS:
            raise ValueError(
                f"Unexpected statement type '{keyword}' in an import batch - only "
                f"SET/INSERT statements are allowed (see catalogue/docs/import-batches.md "
                f"for the expected file format)"
            )

    return statements


def hash_lowest_pyramid_level(path):
    """SHA-256 of only the lowest-resolution pyramid level of every series
    (scene) in the file: every format here is pyramidal, so every series
    already has a tiny lowest-level representation for free, keeping this
    fast regardless of the source file's real size. This matters here
    specifically because, unlike a background crawl, this runs
    synchronously inside a GET request - hashing full-resolution data
    would make the ambiguous-resolution page hang.

    Returns None on any failure (corrupt/unsupported file, or tifffile
    unavailable) rather than raising - a disk match is still shown and
    resolvable without it, just without duplicate-detection.
    """
    if tifffile is None:
        return None
    try:
        with tifffile.TiffFile(path) as tf:
            if len(tf.pages) == 0:
                return None
            hasher = hashlib.sha256()
            for series in tf.series:
                lowest_level = series.levels[-1] if series.levels else series
                pages = lowest_level.pages if hasattr(lowest_level, "pages") else [lowest_level]
                for page in pages:
                    for offset, count in zip(page.dataoffsets, page.databytecounts):
                        tf.filehandle.seek(offset)
                        hasher.update(tf.filehandle.read(count))
            return hasher.hexdigest()
    except Exception:
        return None


def extract_technical_metadata(path):
    """Opens the file just for its header/properties (dimensions, vendor,
    objective magnification) via thumbnail_job.open_slide() - the exact
    same OpenSlide-then-TiffSlide fallback the thumbnail job already uses,
    reused rather than reimplemented. This only reads container metadata,
    not pixel data, so it stays fast even for multi-GB files.

    Returns None on any failure (corrupt/unsupported format) rather than
    raising - a match is still shown and resolvable without it, just
    without technical metadata to compare.
    """
    try:
        slide = thumbnail_job.open_slide(path)
    except Exception:
        return None
    try:
        width, height = slide.dimensions
        properties = slide.properties
        vendor = properties.get("openslide.vendor") or properties.get("tiffslide.vendor")
        magnification = properties.get("openslide.objective-power") or properties.get("tiffslide.objective-power")
        return {
            "width_pixels": width,
            "height_pixels": height,
            "slide_vendor": vendor,
            "objective_magnification": str(magnification) if magnification is not None else None,
        }
    except Exception:
        return None
    finally:
        try:
            slide.close()
        except Exception:
            pass


def find_disk_matches(archive_root_name, filename):
    """Walks ARCHIVE_ROOT/{archive_root_name}/ for every real file matching
    `filename` (case-insensitive basename match) and returns one dict per
    match: {relative_path, physical_path, file_size_bytes, content_hash,
    width_pixels, height_pixels, slide_vendor, objective_magnification}.
    content_hash/technical fields are None where hashing/opening failed -
    still returned, just without duplicate-detection or technical
    comparison for that one match.

    This is what actually distinguishes same-named real files apart: two
    or three same-named files might be true duplicates (identical size and
    hash) or a genuine collision (different files that happen to share a
    name). Grouping by content_hash (when present) is how a caller tells
    these cases apart; equal file_size_bytes with hash=None for both sides
    is the fallback signal (still suggestive, just not conclusive) when
    hashing isn't possible for a given format.
    """
    if not archive_root_name:
        return []

    root = os.path.join(ARCHIVE_ROOT, archive_root_name)
    if not os.path.isdir(root):
        return []

    target = filename.lower()
    matches = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for real_name in filenames:
            if real_name.lower() == target:
                full_path = os.path.join(dirpath, real_name)
                relative_path = os.path.relpath(full_path, ARCHIVE_ROOT)
                technical = extract_technical_metadata(full_path) or {}
                matches.append({
                    "relative_path": relative_path,
                    "physical_path": full_path,
                    "file_size_bytes": os.path.getsize(full_path),
                    "content_hash": hash_lowest_pyramid_level(full_path),
                    "width_pixels": technical.get("width_pixels"),
                    "height_pixels": technical.get("height_pixels"),
                    "slide_vendor": technical.get("slide_vendor"),
                    "objective_magnification": technical.get("objective_magnification"),
                })

    return matches


def _sql_str(value):
    if value is None or value == "":
        return "NULL"
    escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _sql_str_required(value):
    escaped = str(value or "").replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _sql_num(value):
    if value is None or value == "":
        return "NULL"
    return str(value)


def build_ambiguous_resolution_sql(match, source_label, ingestion_method):
    """One statement group for a single resolved real-file match - matches
    a crawler tool's own SQL writer column list and SET @sid :=
    LAST_INSERT_ID() chaining pattern, so commit_batch() can execute it
    exactly the same way it executes the uploaded .sql's own statements.

    `match` is an import_batch_ambiguous_file_matches row (as a dict) with
    resolution='unlinked' - callers must have already filtered out
    'skipped'/'pending' rows before calling this. physical_path always
    comes from the real disk find (find_disk_matches()), never hand-typed -
    there's nothing left to validate here.

    file_size_bytes/width_pixels/height_pixels/objective_magnifications are
    carried straight over from the match row - find_disk_matches() already
    populated these from the real file via
    hash_lowest_pyramid_level()/extract_technical_metadata(), so this is
    just passing along data that already exists, not deriving anything new.
    slide_format is taken from the file extension, matching how normal
    (non-ambiguous) crawled rows populate it.

    Ambiguous matches are always imported with no prior annotation
    history - there is no mechanism in this repo for recovering historical
    annotations for an ambiguous file, only for one a crawler tool matched
    unambiguously and included directly in the uploaded .sql.
    """
    filename = os.path.basename(match["physical_path"])
    physical_path = match["physical_path"]
    archive_relative_path = match.get("relative_path")
    slide_format = os.path.splitext(filename)[1].lstrip(".").upper() or None
    sid_var = f"@sid_match_{match['match_id']}"

    lines = [
        "INSERT INTO slides (filename, physical_path, archive_relative_path, "
        "source, slide_format, file_size_bytes, width_pixels, height_pixels, "
        "objective_magnifications, metadata_status, asset_status, "
        "ingestion_method) VALUES ("
        f"{_sql_str_required(filename)}, {_sql_str_required(physical_path)}, "
        f"{_sql_str(archive_relative_path)}, "
        f"{_sql_str_required(source_label)}, {_sql_str(slide_format)}, "
        f"{_sql_num(match.get('file_size_bytes'))}, "
        f"{_sql_num(match.get('width_pixels'))}, "
        f"{_sql_num(match.get('height_pixels'))}, "
        f"{_sql_str(match.get('objective_magnification'))}, "
        f"'NO_METADATA', 'ACTIVE', "
        f"{_sql_str_required(ingestion_method)});",
        f"SET {sid_var} := LAST_INSERT_ID();",
        f"INSERT INTO slide_metadata (slide_id) VALUES ({sid_var});",
    ]

    return lines


def commit_batch(conn, batch, match_rows, source_label):
    """Executes the batch's uploaded .sql plus one resolution statement
    group per resolved 'unlinked' match (import_batch_ambiguous_file_matches
    rows - one per real file found on disk, not one per ambiguous filename),
    all on the SAME connection/cursor so LAST_INSERT_ID()/@sid_N session
    variables chain correctly across every statement - exactly how a
    crawler tool's own output is designed to run. No CLIENT.MULTI_STATEMENTS
    needed: every statement is executed individually via cur.execute(),
    sequentially, on one connection.

    Tracks every 'INSERT INTO slides' statement's cur.lastrowid as the
    import proceeds - this is how the batch's slide_ids get recorded,
    rather than parsing @sid_N text back out of the SQL afterwards.

    Caller is responsible for the transaction boundary (conn.commit()/
    conn.rollback()) and for closing the connection - this function only
    executes statements and returns the new slide_id list, it never
    commits or rolls back itself, so a caller wrapping this in its own
    try/except can decide what "success" means (e.g. also setting
    provenance_id) before committing.
    """
    with open(os.path.join(batch["_storage_path"], batch["sql_filename"]), "r", encoding="utf-8") as fh:
        base_sql = fh.read()

    statements = validate_batch_sql(base_sql)

    ingestion_method = "crawler tool (web import)"
    for match in match_rows:
        if match["resolution"] == "unlinked":
            statements.extend(
                build_ambiguous_resolution_sql(
                    match, source_label, "crawler tool (ambiguous, web-resolved)"
                )
            )

    new_slide_ids = []
    with conn.cursor() as cur:
        for statement in statements:
            keyword = _leading_keyword(statement)
            if keyword in _TRANSACTION_CONTROL_KEYWORDS:
                # Skipped, not executed - see the module-level comment on
                # _ALLOWED_BATCH_KEYWORDS for why.
                continue
            cur.execute(statement)
            if keyword == "INSERT" and re.match(
                r"^\s*INSERT\s+INTO\s+slides\b", _strip_leading_comments(statement), re.IGNORECASE
            ):
                new_slide_ids.append(cur.lastrowid)

    return new_slide_ids
