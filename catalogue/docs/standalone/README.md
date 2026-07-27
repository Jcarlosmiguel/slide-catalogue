# Standalone deployment: nginx examples

This catalogue can be deployed three ways, in increasing order of
complexity. Each tier is a real, complete option - not every deployment
needs to end up at Tier 3.

| Tier | What it is | Files |
|---|---|---|
| 1. Basic | Plain HTTP on a real domain. What the repo ships and runs by default (`catalogue/nginx/catalogue.dev.conf`), just with a real `server_name`. | `nginx.basic.conf.example` |
| 2. Self-signed HTTPS | Same app, encrypted, using a certificate this repo generates itself - no external certificate authority involved. | `nginx.selfsigned.conf.example`, `generate_selfsigned_cert.sh` |
| 3. Full, alongside OMERO | This catalogue sharing one public IP/nginx with an existing OMERO deployment, each on its own domain. A different integration pattern entirely, not just "Tier 2 plus OMERO". | [`../omero-integration/`](../omero-integration/) |

If you don't have (and don't plan to run) OMERO at all, stop at Tier 1
or 2 - Tier 3 is a separate document for a specifically different
deployment shape, not a further step up from Tier 2.

## Tier 1: Basic (HTTP only)

Nothing to generate. Copy `nginx.basic.conf.example` over
`catalogue/nginx/catalogue.dev.conf` (or point `compose.yaml`'s
`catalogue_nginx` volume mount at this file directly), replace
`yourdomain.com` with your real domain, and make sure that domain's DNS
actually points here.

No `compose.yaml` changes needed - `catalogue_nginx` already publishes
`${HTTP_PORT}:80`, so a real standalone deployment on the standard web
port is just:

```bash
# in .env
HTTP_PORT=80
```

```bash
docker compose up -d catalogue_nginx
```

Fine for trying the app out or sitting behind something else that
already terminates TLS. Not fine for real user accounts on the open
internet - see Tier 2.

## Tier 2: Self-signed HTTPS

1. **Generate the certificate:**

   ```bash
   ./generate_selfsigned_cert.sh
   ```

   Reads the domain from `APP_BASE_URL` in your `.env` (prompts if it's
   unset), and writes `fullchain.pem`, `<domain>.key`, and `ffdhe2048.pem`
   into `certs/nginx/` at the repo root. Safe to re-run - refuses to
   overwrite a real, CA-issued certificate that's already there unless
   you pass `--force`. `--dry-run` previews without writing anything.

2. **Mount the certs and open 443.** Add to `catalogue_nginx` in
   `compose.yaml`:

   ```yaml
   catalogue_nginx:
     ports:
       - "${HTTP_PORT}:80"
       - "443:443"          # add this
     volumes:
       - ./catalogue/frontend:/usr/share/nginx/html:ro
       - ./catalogue/thumbnails:/srv/thumbnails:ro
       - ./catalogue/documents:/srv/documents:ro
       - ./catalogue/nginx/catalogue.dev.conf:/etc/nginx/conf.d/default.conf:ro
       # swap the line above for the one below once you've copied
       # nginx.selfsigned.conf.example into place (see step 3):
       # - ./catalogue/nginx/catalogue.conf:/etc/nginx/conf.d/default.conf:ro
       - ./certs/nginx:/etc/nginx/ssl:ro     # add this
   ```

3. **Use the HTTPS config.** Copy `nginx.selfsigned.conf.example` to
   e.g. `catalogue/nginx/catalogue.conf`, replace `yourdomain.com`
   throughout (both the `server_name` lines and the `ssl_certificate_key`
   filename need to match), and point the volume mount above at it.

4. **Go HTTPS-only in the app itself.** In `.env`:

   ```bash
   APP_COOKIE_SECURE=true
   APP_BASE_URL=https://yourdomain.com
   ```

   Do this only *after* HTTPS is actually serving - a secure-only
   session cookie set while still reachable over plain HTTP gets
   silently dropped by the browser.

   ```bash
   docker compose up -d catalogue_backend catalogue_nginx
   ```

Browsers will show a one-time trust warning for a self-signed
certificate - expected, not a bug. Swap in a real certificate later
(e.g. Let's Encrypt) by replacing the two files in `certs/nginx/` in
place; nothing in `nginx.selfsigned.conf.example` needs to change
either way.

## Tier 3: Full, alongside OMERO

See [`../omero-integration/`](../omero-integration/README.md) - a
genuinely different deployment shape (one shared nginx routing by
domain to two independent apps), not built on top of Tiers 1/2 above.
