# DICOM support

The catalogue can store DICOM slides alongside the usual NDPI/SCN/SVS
whole-slide images - added for the (currently hypothetical, not in use on
this deployment) case of a collection with real DICOM content, e.g. a
medical school radiology archive.

DICOM headers routinely embed real patient-identifying data directly in
the file (name, ID, birth date, address, referring/performing physician,
institution, accession number) - a different and generally more serious
concern than this catalogue's existing human-specimen provenance handling.
Every DICOM file must be de-identified before the catalogue ever indexes
or serves it - there is no path that skips this.

## De-identification modes

Two modes, both implemented in `backend/app/dicom_deidentify.py` (and its
byte-identical copy in `slide-crawler`'s own package, see below):

- **`full`** - complete anonymiser. Removes every direct identifier AND
  every descriptive field that could narrow down who the patient is even
  indirectly (age, size, weight, free-text descriptions, dates/times).
  Only the technical imaging data needed to display the image is left.
- **`non_identifying`** - partial, teaching-value-preserving. Removes
  every direct identifier but keeps non-identifying descriptive fields
  with real teaching value (sex, age, body part examined, modality,
  study/series description, imaging parameters). A practical subset of
  the DICOM standard's own PS3.15 Basic De-identification Profile, not a
  certified implementation of it.

Both modes also regenerate `StudyInstanceUID`/`SeriesInstanceUID`/
`SOPInstanceUID` (consistently across every file processed in the same
run, so files from the same original study/series still share the same
new UIDs) so a de-identified file can't be linked back to the source
system's own records via UID lookup.

**Neither mode inspects pixel data.** A scanner-burned-in text overlay
(patient name printed directly onto the image) is not detected or removed
by either mode. If a source file's own `BurnedInAnnotation` tag says
`YES`, the slide is flagged (`slides.dicom_burned_in_annotation_warning`)
and needs manual visual review before being made available, regardless of
which mode was used.

## Where de-identification happens

**slide-crawler** is the primary ingestion path. If DICOM files are found
during a crawl (see `--extensions`, below), it stops and asks which mode
to use, showing the full description of each mode first - never just a
bare flag name - matching `--dicom-deidentify-mode` if that was already
supplied for an unattended run. It then writes a de-identified **copy** of
each DICOM file to `--dicom-output-dir` and generates SQL that references
only that copy (`slides.physical_path`) - the original source file is
never modified and never read from again. Detection is opt-in: include
`dcm` in `--extensions` and the crawler will match `.dcm` files by
extension AND content-sniff every other file for the DICOM signature
(`DICM` at byte offset 128), since real DICOM exports very commonly have
no extension at all. Without `dcm` in `--extensions`, DICOM detection
never runs and a crawl behaves exactly as it always has - zero overhead
for the common non-DICOM case.

**The catalogue backend is a safety net, not a second ingestion path.**
`slides.dicom_deidentification_mode` records which mode (if any) a DICOM
slide has been through. Both `app/thumbnail_job.py` (the sysadmin Import
Batches thumbnail job) and `catalogue/tools/populate_new_slide_thumbnails.py`
refuse to read a DICOM slide's file at all - not even for a thumbnail -
if this column is `NULL`. This is the backstop for a DICOM slide that
reached `slides` some other way than slide-crawler's own de-identification
step (e.g. a direct SQL import). The sysadmin System Settings page
(`admin/admin-settings.html`) has a site-wide default mode
(`system_settings.dicom_deidentification_default_mode`, defaults to
`full`) for whenever the catalogue itself needs to de-identify a DICOM
file - each mode's full description is shown inline on that page, not
just the setting name.

## Thumbnails

Most real-world DICOM teaching content (radiology: CT/MRI/X-ray) is
single- or multi-frame, not the newer WSI-pyramid DICOM subset OpenSlide
4.x added support for - so DICOM thumbnails are generated independently
of the OpenSlide/TiffSlide pipeline used for every other format, via
`pydicom` pixel data + basic window/level normalization
(`RescaleSlope`/`RescaleIntercept`/`WindowCenter`/`WindowWidth`, falling
back to min-max normalization if no window hint is present in the file).
A multi-frame file's middle frame is used as the representative preview.
DICOM pixel data is never touched by de-identification (only header tags
are), so this is always safe to run once `dicom_deidentification_mode` is
set.

## Schema

`migrations/0017_add_slide_dicom_deidentification.sql` adds:

- `slides.dicom_deidentification_mode` (`ENUM('full','non_identifying')`,
  `NULL` for every non-DICOM slide, and for a DICOM slide not yet
  de-identified)
- `slides.dicom_burned_in_annotation_warning` (`TINYINT(1)`, see above)
- seeds `system_settings.dicom_deidentification_default_mode = 'full'`

## Deployment: a new volume mount, only if this is actually used

Not needed today on this deployment (no DICOM content in use), but if a
future collection does use this: `slides.physical_path` for a DICOM slide
points into whichever folder `slide-crawler --dicom-output-dir` wrote the
de-identified copies to, exposed through `--dicom-physical-path-prefix` -
a **separate** store from the read-only archive mount every other slide
format uses (see `--physical-path-prefix` vs `--dicom-physical-path-prefix`
in slide-crawler's own README). `catalogue_backend` and the nginx
container need a new volume mount for that folder before any DICOM slide
can actually be read/served, matching the existing pattern for
`/srv/archive` (the main archive) and `/srv/thumbnails` in
`compose.yaml`.
