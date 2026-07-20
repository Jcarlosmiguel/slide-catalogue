# omero-mvls

Containerized OMERO deployment for MVLS, with the MVLS Virtual
Microscopy Catalogue app merged in behind the same nginx / same public
IP.

## How it fits together

One shared `nginx` container routes by domain:

- `omero.mvls.gla.ac.uk` -> `nginx` -> OMERO.web (`omeroweb` container)
- `catalogue.mvls.gla.ac.uk` -> `nginx` -> `catalogue_nginx` -> `catalogue_backend` -> `catalogue_mariadb`

Both domains are covered by a single SAN certificate. OMERO itself
(`omeroserver`, `database` - Postgres) and the catalogue app
(`catalogue_backend`, `catalogue_mariadb`) are otherwise independent -
separate databases, separate networks, only sharing the nginx front
door.

## Getting started

```bash
cp docs/dotenv .env
nano .env                 # fill in every CHANGE_ME - see comments in the file
docker compose up -d
```

Full walkthrough (localhost first, then a real domain, then SSL):
`docs/setup.md`.

## Where to look

| Folder | What's there |
|---|---|
| `docs/` | Setup/certificate/backup documentation and the sanitized config templates (`dotenv`, `nginx.conf.template`, `extra.omero.template`, `extraweb.omero.template`). Start here for how anything works. |
| `scripts/` | All operational scripts - `certificates.sh`/`self_certificates.sh` (TLS), `backup_omero.sh`/`restore_omero.sh`/`backup_catalogue.sh`/`restore_catalogue.sh`/`backup_all.sh` (databases). All support `--dry-run`. See `scripts/README.md` for a quick reference table. |
| `nginx/` | The live `nginx.conf` - hand-maintained, not auto-generated. Domain routing for both apps lives here. |
| `omero_config/` | `extra.omero` (OMERO server config) and `extraweb.omero` (OMERO.web config) - applied on every container start. |
| `certs/` | Certificate/key material. Not committed except `README.md`-style notes - see `docs/certificates.md`. |
| `logo/` | Logo image served by nginx at `/images/`, referenced by `omero.web.login_logo`. |
| `backups/` | OMERO Postgres dumps (`backup_omero.sh`'s output). |
| `catalogue/` | The catalogue app itself (transferred via `scp`, not git - see `catalogue/README.md`). Its own database backups live in `catalogue/backups/`. |

## Enabling docker for your user (one-time, per host)

```bash
sudo groupadd docker
sudo usermod -aG docker $USER
```

## Useful commands

```bash
docker compose exec omeroserver bash
docker compose exec omeroweb bash
```

## Background

How the catalogue merge itself was done, and what was found/fixed along
the way: `docs/merge-history.md`.
