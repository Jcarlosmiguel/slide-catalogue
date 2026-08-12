# Import Batches

The sysadmin "Import Batches" page (`sysadmin/import-batches.html`,
`sysadmin/import-batch.html`) lets a system administrator upload the
output of an external slide-crawling tool through the browser instead of
piping a `.sql` dump into the database by hand: upload a matching
`.sql`/`.report.txt`/`.run.log` trio, resolve any ambiguous filenames
against real files on disk, record provenance, then commit as one atomic
import with fresh `slide_id`s.

No crawler tool ships in this repo. This page is a generic front end for
any tool that produces output in the shape documented below - build your
own, or adapt an existing crawler's output format to match.

## Expected files

**`.sql`** - `SET`/`INSERT` statements only (see `admin_sql.py`'s
`BLOCKED_KEYWORDS` for what's rejected). Uses the same
`SET @sid := LAST_INSERT_ID();` chaining pattern after each
`INSERT INTO slides (...)` as the rest of this codebase's own SQL
generation, so statements that reference the just-inserted slide (e.g.
`INSERT INTO slide_metadata (slide_id) VALUES (@sid)`) run correctly in
sequence. `START TRANSACTION;`/`COMMIT;` may be present but are ignored -
this page's own commit is the real transaction boundary.

**`.report.txt`** - plain text, line-prefix based. Only the lines below
are parsed; everything else is ignored, so a tool is free to include
additional human-readable detail:

```
Crawled folder: /path/the/tool/crawled

Real files crawled: 1234
  linked: 1000
  share-only (no external record): 200
  ambiguous (matched >1 folder): 34
external records with no matching real file (orphans): 12

Region annotations imported: 500 across 300 slides

Ambiguous filenames (not auto-resolved, review manually):
  some-file.ndpi -> /path/one, /path/two
  another-file.svs -> /path/three, /path/four
```

`Crawled folder:` supplies the archive subfolder name that ambiguous-file
disk lookups get scoped to (`SHARE_ROOT_LINUX/{that folder}/`). The
`Ambiguous filenames` section may repeat the same filename more than once
(once per real physical file sharing that name) - this page deduplicates
by filename automatically, merging candidate folders across every
occurrence.

**`.run.log`** - stored for reference and downloadable from the batch
page; not parsed.

## Resolving ambiguous files

A filename reported as ambiguous is deliberately left out of the `.sql` -
this page finds every real file on disk matching that name
(`import_batches.py`'s `find_disk_matches()`), hashes the lowest-resolution
pyramid level of each (fast even for huge files) and reads basic technical
metadata (dimensions, vendor, objective magnification) via
OpenSlide/TiffSlide, so a sysadmin can tell whether same-named files are
true duplicates or a genuine collision. Each real file is resolved
independently as **unlinked** (import as a new slide, with no prior
annotation history) or **skipped** (don't import it).
