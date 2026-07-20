# scripts/

Operational scripts for this deployment. Full explanations live in
`../docs/certificates.md` and `../docs/backups.md` - this is just a
quick reference for what's here and how to invoke it.

All of them resolve `.env`/`compose.yaml`/`certs/`/`nginx/` against
their own parent directory, so they work identically whether run as
`scripts/x.sh` from the project root or as `cd scripts && ./x.sh`.

## Certificates

| Script | Purpose | Flags | sudo |
|---|---|---|---|
| `certificates.sh` | Sync an IT-issued cert from `CERTLOCATION`/`PEMLOCATION` into `certs/`, repackage for OMERO, fix ownership. Safe to re-run routinely (renewals, cron) - reports `UP TO DATE` or `RENEWAL DETECTED`/`APPLIED`. | `--dry-run` | Yes |
| `self_certificates.sh` | Bootstrap a self-signed cert when there's no real one yet. Refuses to overwrite an existing CA-issued-looking cert. | `--dry-run`, `--force` | Yes |

## Backups / restores

| Script | Purpose | Flags | sudo |
|---|---|---|---|
| `backup_omero.sh` | Back up the OMERO Postgres database to `./backups/`. | `--dry-run` | No |
| `restore_omero.sh` | Interactively restore an OMERO Postgres backup. Warns and requires typing `UPGRADE` on a Postgres major-version mismatch. | `--dry-run` | No |
| `backup_catalogue.sh` | Back up the Catalogue MariaDB database to `catalogue/backups/database/full/`. | `--dry-run` | No |
| `restore_catalogue.sh` | Interactively restore a Catalogue MariaDB backup. | `--dry-run` | No |
| `backup_all.sh` | Runs `backup_omero.sh` then `backup_catalogue.sh`. One failing doesn't stop the other; exits non-zero if either did. No `restore_all.sh` equivalent - restoring both together isn't something to do casually. | `--dry-run` (passed through to both) | Yes |

## Quick examples

```bash
scripts/certificates.sh --dry-run          # preview a cert renewal
scripts/self_certificates.sh               # bootstrap a self-signed cert for local/test use
scripts/backup_all.sh                      # back up both databases (needs sudo)
scripts/restore_omero.sh                   # interactively restore OMERO's database
```
