# Integrating this catalogue with an existing OMERO deployment

This repo is a standalone catalogue app - it doesn't include, manage, or
depend on OMERO. But it was originally built to run alongside an OMERO
deployment, sharing one public IP and one nginx, routed by domain. This
folder documents that integration pattern in case you want to run it the
same way, using sanitized example files instead of the real (private)
deployment.

Not needed at all for a standalone deployment - see the top-level
`README.md` and `docs/deployment.md` for that.

## Files in this folder

| File | What it shows |
|---|---|
| `compose.example.yaml` | How to add the catalogue's services to an existing OMERO `compose.yaml` - a minimal OMERO sketch for context, plus the catalogue services (copied unmodified from this repo's real `compose.yaml`), plus the one network change OMERO's own `nginx` service needs. |
| `nginx.conf.example` | The shared nginx config that routes by domain: `omero.yourdomain.com` to OMERO, `catalogue.yourdomain.com` to the catalogue. This is the only piece that needs to know about both apps. |
| `.env.example` | Every environment variable both `compose.example.yaml` and `nginx.conf.example` reference, with `CHANGE_ME` placeholders for anything secret or site-specific. |

## The integration, in short

One shared `nginx` container routes by domain:

```text
omero.yourdomain.com      -> nginx -> omeroweb
catalogue.yourdomain.com  -> nginx -> catalogue_nginx -> catalogue_backend -> catalogue_mariadb
```

OMERO (Postgres) and the catalogue (MariaDB) stay fully independent -
separate databases, separate Docker networks, only sharing the nginx
front door. The only change on the OMERO side is adding `catalogue_net`
to its `nginx` service's networks, so that one container can reach
`catalogue_nginx` by name.

## Applying this to your own deployment

1. **Copy the catalogue services.** Copy the `catalogue_*` services (and
   the `catalogue_net` network / `catalogue_mariadb_data` volume) from
   `compose.example.yaml` into your existing OMERO `compose.yaml`. Add
   `catalogue_net` to your existing `nginx` service's `networks:` list.
   This repo's `catalogue/` folder should sit alongside your OMERO
   compose file (e.g. `./catalogue/backend`, `./catalogue/frontend`).

2. **Merge the environment variables.** Add the "Catalogue app" section
   from `.env.example` to your existing `.env` (skip the OMERO-side
   variables if you already have equivalents).

3. **Replace your nginx config**, or merge `nginx.conf.example`'s two
   `server {}` blocks (OMERO and catalogue) into your existing one.
   Replace `omero.yourdomain.com` / `catalogue.yourdomain.com` with your
   real domains.

4. **Bring the catalogue services up on their own first** and verify
   directly on its own port (`http://<server-ip>:8080`, from `HTTP_PORT`
   in `.env`) before touching the shared nginx - that way you're never
   debugging a live, already-serving OMERO instance at the same time as
   a brand-new deployment.

   ```bash
   docker compose up -d catalogue_mariadb catalogue_backend catalogue_nginx
   ```

5. **Run the catalogue's database migrations and seed data** - see the
   top-level `README.md` for the exact commands
   (`run_migrations.sh` / `seed_example_data.py`).

6. **Cut over the shared nginx last**, since that's the only step that
   touches already-serving OMERO traffic:

   ```bash
   docker compose up -d nginx
   ```

7. **HTTPS**, once you're ready: uncomment the HTTPS `server {}` blocks
   in your nginx config once you have a certificate, then flip
   `APP_COOKIE_SECURE=true` and update `APP_BASE_URL` to `https://` in
   `.env` - a secure-only session cookie set while still served over
   plain HTTP gets silently dropped by the browser, so these two changes
   need to happen together, after the domain is actually behind HTTPS,
   not before.

   ```bash
   docker compose up -d catalogue_backend
   ```

## Why domain-routing rather than a path prefix

Routing by domain (`omero.yourdomain.com` vs `catalogue.yourdomain.com`)
rather than by path (`yourdomain.com/omero` vs `yourdomain.com/catalogue`)
avoids needing to rewrite either app's internal absolute paths/links to
work under a subpath - both apps can stay exactly as they'd behave
standalone.
