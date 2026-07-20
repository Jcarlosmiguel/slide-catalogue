# From localhost to your own domain

Takes the generic `docs/dotenv` and `docs/nginx.conf.template` files
from "just downloaded this" to "running on my own domain." Assumes a
fresh checkout with no `.env` or `nginx/nginx.conf` in place yet.

See `docs/certificates.md` for how the certificate side of this
(self-signed vs real) actually works - this doc just says when to get
one.

---

## Part 1 - Quickstart on localhost

**What actually happens if you just copy the templates and run
`docker compose up -d`:**

```bash
cp docs/dotenv .env
cp docs/nginx.conf.template nginx/nginx.conf
cp docs/extra.omero.template omero_config/extra.omero
cp docs/extraweb.omero.template omero_config/extraweb.omero
```

The two `omero_config` templates work as-is on localhost with no
editing - everything site-specific in them (the login logo, CSRF
origins, iframe-embedding, the public viewing account) is commented out
by default. The one line worth a glance before your first real
production start is `omero.jvmcfg.system.memory 4096` in
`extra.omero.template` - 4GB is enough to boot and test with, not a
production sizing recommendation (see the comment above it in the file
for the reasoning).

Then fill in `.env`'s `CHANGE_ME` values. For a local/localhost test,
most of them can take simple placeholder values, but a few need a
*real* value even locally, because Docker will otherwise try to use the
literal text `CHANGE_ME` as a filesystem path or a real credential:

- `OMEROFILESEXTERNALPATH` - must be a real path on your machine (e.g. `./OMERO-data`). Docker will silently create a folder literally named `CHANGE_ME` if you leave this as-is, and OMERO will start against that empty folder.
- `MARIADB_ROOT_PASSWORD`, `MARIADB_PASSWORD`, `OMEROPGPASSWORD`, `OMEROROOTPASSWORD`, `OMEROGLACIER2ICESSLPASSWORD`, `APP_SESSION_SECRET` - anything is fine for a local test (they don't need to be *good* passwords yet, just not literally blank), but they can't be left unset or some services will fail to start.
- `FULLDOMAIN`, `EMAILSSL`, `SMTP_*`, `SHARE_ROOT_*`, `APP_BASE_URL` - safe to leave as obviously-fake placeholders (e.g. `localhost`, `test@example.com`) for a local test - nothing checks these at startup, they only matter once you're sending real email or expecting a real domain to resolve.

Check you got them all:

```bash
grep -c CHANGE_ME .env   # must print 0
```

Then:

```bash
docker compose up -d
```

**Once it's up, here's what you can actually reach and how:**

| What you want | URL | Notes |
|---|---|---|
| OMERO | `http://localhost/` | Works as-is - the OMERO server block's `server_name` explicitly includes `localhost` alongside `omero.yourdomain.com`. |
| Catalogue | `http://localhost:8080/` | `catalogue_nginx`'s own direct port, independent of domain-based routing entirely. This works regardless of what `nginx.conf` says. |
| Catalogue via the "real" domain routing | `http://catalogue.yourdomain.com/` won't resolve on your machine | Either add `127.0.0.1 omero.yourdomain.com catalogue.yourdomain.com` to `/etc/hosts` (or `C:\Windows\System32\drivers\etc\hosts` on Windows) so those names resolve locally, or test with `curl -H "Host: catalogue.yourdomain.com" http://localhost/` instead. |

HTTPS (443) isn't reachable at all yet - the template's HTTPS blocks are
commented out on purpose, since there's no certificate to serve. That's
Part 2.

---

## Part 2 - Moving to your own domain

Once you have a real domain (or two, if catalogue is separate) pointing
at this server's IP, do this in order:

### 2.1 - Point DNS at the server

Create A (and AAAA, if you have IPv6) records for both domains pointing
at the server's public IP. Confirm they resolve before continuing:

```bash
ping omero.yourdomain.com
ping catalogue.yourdomain.com
```

### 2.2 - Replace the domain placeholders

In `.env`, edit these three values directly (a text editor is simplest
here - there are only three, and they're not identical strings, so a
find-and-replace one-liner doesn't save much):

- `FULLDOMAIN` -> your real OMERO domain
- `EMAILSSL` -> your real admin/SSL contact email
- `APP_BASE_URL` -> `http://` + your real catalogue domain (this becomes `https://` later, in 2.5)

In `nginx/nginx.conf`, replace every occurrence of `omero.yourdomain.com`
and `catalogue.yourdomain.com` with your real domains:

```bash
sed -i 's/omero\.yourdomain\.com/your-real-omero-domain/g; s/catalogue\.yourdomain\.com/your-real-catalogue-domain/g' nginx/nginx.conf
```

Validate before restarting anything:

```bash
docker compose config > /dev/null && echo "compose OK"
```

### 2.3 - Get a certificate, enable HTTPS

Self-signed or real - see `docs/certificates.md` for the actual
generation step (`scripts/self_certificates.sh` or
`scripts/certificates.sh`). Once the cert files exist in `certs/nginx/`:

For each domain's commented HTTPS `server { }` block in `nginx.conf`:

1. Uncomment the whole block.
2. Make sure its `ssl_certificate`/`ssl_certificate_key` lines point at whichever cert you actually generated/obtained.
3. Optionally replace that domain's active plain-HTTP block with a redirect-to-HTTPS instead (an example is included right after each HTTPS block in the template).

Validate, then apply:

```bash
docker compose config > /dev/null && echo "compose OK"
docker compose up -d nginx
```

In `omero_config/extraweb.omero`, uncomment two settings now that OMERO
itself is behind HTTPS (both are commented out by default precisely
because they'd break things if enabled too early, per the comments
above each in the template):

- `omero.web.secure True` - same reasoning as catalogue's `APP_COOKIE_SECURE` below: a secure-only cookie set while still on plain HTTP gets silently dropped by the browser.
- `omero.web.csrf_trusted_origins '["https://omero.yourdomain.com"]'` - replace with your real domain. Without this, OMERO.web rejects legitimate login/API requests with a CSRF error once it's actually being accessed over HTTPS on a real domain.

Apply:

```bash
docker compose up -d omeroweb
```

### 2.4 - Verify

```bash
curl -I http://your-real-omero-domain/       # 200, or 301 if you added a redirect
curl -kI https://your-real-omero-domain/     # 200 (or 301 to /webclient/, which is normal)
curl -I http://your-real-catalogue-domain/
curl -kI https://your-real-catalogue-domain/
```

If you added a redirect in 2.3, also confirm plain HTTP now redirects
rather than serving content directly.

### 2.5 - If catalogue is part of this deployment

Flip `APP_COOKIE_SECURE=true` in `.env` and update `APP_BASE_URL` to the
`https://` form once catalogue itself is behind HTTPS - the session
cookie won't be sent at all if this is out of sync with which protocol
is actually serving the domain. Then:

```bash
docker compose up -d catalogue_backend
```
