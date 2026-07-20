# How the catalogue merge was done

Condensed record of merging the MVLS Catalogue app into this compose
stack, so it sits behind the same nginx / same public IP as OMERO. The
actual diffs now live in `compose.yaml`/`nginx/nginx.conf`/git history
directly - this is the reasoning and sequence, not a byte-for-byte
change log.

## Facts the merge relied on

- `omero.mvls.gla.ac.uk` and `catalogue.mvls.gla.ac.uk` resolve to the same server IP.
- `certs/nginx/fullchain.pem` is a single Let's Encrypt cert whose SAN list covers **both** domains (renewal is IT's responsibility).
- No port, network, or volume name collisions existed between the two projects.
- No self-hosted mail service - catalogue uses the Gmail relay already configured, decided against a self-hosted mail service (disk-space concern) and O365 (MFA/shared-mailbox complexity).
- Catalogue launched on plain port 80 first; the move to 443 was a deliberate later step, done once testing was complete.
- `catalogue/` (the whole app payload, including thumbnails) was transferred by `scp`, not git - thumbnails aren't part of mvls-catalogue's git history (gitignored there), so a clone alone wouldn't have brought them over.

## Sequence

1. **Prep** - picked a `.gitignore` strategy (see `docs/gitignore.omero-mvls-catalogue-*`), created a throwaway branch so `main` stayed a clean rollback point, backed up `.env` (the one thing git can't help with).
2. **Transfer** - `scp`'d `catalogue/` directly onto the server.
3. **Apply** - appended catalogue's variables to `.env`, replaced `compose.yaml`/`nginx/nginx.conf` wholesale with the merged versions, added the new `scripts/` (backup/restore/certificate scripts), committed as one checkpoint on the branch.
4. **Bring up, staged** - started the catalogue services on their own first (verified standalone on `:8080` before touching anything live), then cut over the shared `nginx` last, since that's the only step that touches already-serving traffic.
5. **Later: HTTPS** - moved catalogue from port 80 to 443 once testing was done, as its own deliberate step - flipping `APP_COOKIE_SECURE`/`omero.web.secure` before the domain was actually behind HTTPS would have silently broken login (secure-only cookies get dropped over plain HTTP).

## Real issues found and fixed along the way

- `certificates.sh` could silently regenerate `nginx.conf` from a hardcoded single-domain template on every cert renewal, reverting the whole merge back to omero-only - removed that regeneration entirely (see `docs/certificates.md`).
- `restore_database.sh`'s Postgres readiness check was missing `</dev/null`, silently eating input meant for later interactive prompts under non-interactive/scripted use - fixed in `restore_omero.sh` (see `docs/backups.md`).
- `extraweb.omero` shipped a guessable public-viewing-account password and a `cors_origin_allow_all True` that made an adjacent CORS whitelist pointless - the sanitized template makes both explicitly opt-in instead of on by default.
- `server.p12` never got an explicit `chmod` in the original `certificates.sh` - its permissions depended entirely on ambient umask despite embedding a password-protected private key - now `chmod 600` explicitly.
- `PERMISSIONS` (an `.env` var) and the nginx.conf auto-regeneration's `NGINX_PORT_GENERAL`/`NGINX_PORT_SECURE` all became genuinely dead once the above were fixed - removed from `certificates.sh`'s required-vars check.

## What's an ongoing reference vs. what was one-time

Still relevant day to day: `docs/setup.md`, `docs/certificates.md`,
`docs/backups.md`, the templates in `docs/`, and everything in
`scripts/`. The staging files used only to *apply* the merge itself
(full drop-in `compose.yaml`/`nginx.conf` copies, `.env` diffs) aren't
carried forward here - once applied, `compose.yaml` and
`nginx/nginx.conf` *are* that content, and `git log`/`git diff` on the
real files are more authoritative than a static snapshot of what they
used to need to become.
