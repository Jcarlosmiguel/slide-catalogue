"""Propagates the stain_dictionary curated "Comparison slide" convention
onto slides.

stain_dictionary already has curated entries (e.g. "a) H&E b) PAS") with
stain_family = 'Comparison slide' - real expert-authored comparison-slide
combinations, not something detected from a filename (that distinction
requires actually looking at the image; see docs/database.md's
stain_dictionary section). This module is the shared sync logic used both
by the sysadmin Maintenance Jobs button and, for a single slide at a time,
by admin_apply_metadata_correction when a stain correction is applied.
"""


def sync(conn):
    """Additive only: sets slide_metadata.is_comparison_slide = 1 for
    every slide whose stain matches a stain_dictionary row with
    stain_family = 'Comparison slide', wherever it isn't already 1. Never
    resets an existing TRUE and never sets FALSE - curators un-flag
    individually if something was wrongly marked, same as any other
    manual metadata fact. Runs inside the caller's own transaction -
    commit/rollback is the caller's responsibility."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.slide_id
            FROM slides s
            JOIN slide_metadata sm ON sm.slide_id = s.slide_id
            JOIN stain_dictionary sd ON sd.original_stain = sm.stain
            WHERE sd.stain_family = 'Comparison slide'
              AND (sm.is_comparison_slide IS NULL OR sm.is_comparison_slide = 0)
            """
        )
        slide_ids = [row["slide_id"] for row in cur.fetchall()]

        for slide_id in slide_ids:
            cur.execute(
                "UPDATE slide_metadata SET is_comparison_slide = 1 WHERE slide_id = %s",
                (slide_id,),
            )

    return [{"slide_id": sid, "status": "MARKED_CMP", "error": None} for sid in slide_ids]
