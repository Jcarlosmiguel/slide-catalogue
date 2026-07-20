# Certificates

Two scripts, two different jobs - deliberately not one script with a
mode flag:

- **`scripts/certificates.sh`** - syncs an already-issued certificate
  from wherever IT/certbot/ACME drops it on the host (`CERTLOCATION`/
  `PEMLOCATION` in `.env`) into the docker-mounted `certs/` folders, and
  repackages it for OMERO (`server.pem`/`.key`/`.p12`, DH params). Meant
  to be re-run routinely - every renewal, possibly from cron - so it
  stays fully non-interactive by design.
- **`scripts/self_certificates.sh`** - bootstraps a self-signed
  certificate for when there's no real one yet (fresh/local/test
  deployments). Writes to the exact same target files `certificates.sh`
  produces, so `nginx.conf`/`extra.omero` don't care which script
  populated them.

Folding self-signed generation into `certificates.sh` via an interactive
prompt was considered and rejected: it would mean either suppressing
that prompt on every automated renewal run, or risking a fat-fingered
"yes" during a routine IT renewal overwriting a real certificate with a
throwaway one. Two scripts keeps `certificates.sh` exactly as safe and
scriptable as it needs to be.

## Both support `--dry-run`

Prints exactly what would happen (files created/copied/chmod'd/chown'd)
without changing anything. Validation/verification steps still run for
real - an accurate preview needs them. `certificates.sh`'s DH parameter
generation (the slowest step by far - real CPU work) is skipped
entirely under `--dry-run` rather than done "for preview" and thrown
away.

```bash
scripts/certificates.sh --dry-run
scripts/self_certificates.sh --dry-run
```

Tested against real throwaway cert/key files (both scripts) and a real
mini local CA (for the protection check below) - confirmed zero files
created under `--dry-run` in every case.

## Is this actually a renewal, or already up to date?

`certificates.sh` prints an explicit banner after comparing the
`CERTLOCATION`/`PEMLOCATION` source files against what's already
deployed in `certs/nginx/` (byte-for-byte, via `cmp`):

```
UP TO DATE - cert and key in CERTLOCATION/PEMLOCATION are
identical to what's already deployed in certs/nginx/. Nothing to update.
```

or

```
RENEWAL DETECTED - cert and/or key in CERTLOCATION/PEMLOCATION
differ from what's currently in certs/nginx/
```

(`RENEWAL APPLIED` instead of `RENEWAL DETECTED` outside `--dry-run`,
once the copy has actually happened.) Same comparison runs in both
modes, so the banner is accurate whether or not anything gets written.
It also confirms it actually found files at `CERTLOCATION`/
`PEMLOCATION` before going any further, and warns if a renewed
certificate's SAN list stops mentioning "catalogue" - this deployment's
cert is expected to cover both `omero.mvls.gla.ac.uk` and
`catalogue.mvls.gla.ac.uk`.

## Real-certificate protection in `self_certificates.sh`

Before generating anything, it checks whether a certificate already
exists at the target path and inspects it: a self-signed certificate's
Issuer and Subject are identical (it signed itself); a real CA-issued
certificate's aren't. If they differ, it refuses to overwrite and exits
- `--force` overrides. Verified against a real two-step local CA (root
cert + a leaf cert signed by it, so Issuer != Subject like a genuine
certificate) to confirm the block, and the `--force` override, both
work.

## Dependencies

`self_certificates.sh` checks for `openssl` up front and gives an
actionable error (with install commands for Debian/Ubuntu and
RHEL/Fedora) if it's missing, rather than failing partway through with
a confusing "command not found."

## Everything else `certificates.sh` does

Copies cert+key into `certs/nginx/`, verifies the cert and key actually
match (`openssl x509`/`openssl rsa` modulus comparison), repackages for
OMERO into `certs/omero/server.pem`/`.key`/`.p12` (the `.p12` password
comes from `OMEROGLACIER2ICESSLPASSWORD` in `.env`), generates/reuses DH
parameters, and fixes ownership (`chown -R 1000:1000`) so the containers
can read everything regardless of which user ran the script. Requires
`sudo` - fails fast with a clear message otherwise, rather than silently
mixing root-owned and user-owned output files (some internal commands
are `sudo`-prefixed, some aren't, carried over from the original
script).

**It does not touch `nginx.conf`.** The original version of this script
could regenerate `nginx.conf` from a hardcoded single-domain template on
every renewal if answered "y" to its overwrite prompt - since
`nginx.conf` is now a hand-maintained file covering both
`omero.mvls.gla.ac.uk` and `catalogue.mvls.gla.ac.uk` plus CORS headers
and the `/images/` logo location, that regeneration would have silently
reverted all of it back to omero-only. Removed entirely; if `nginx.conf`
itself needs to change, edit it directly and review with `git diff` /
`nginx -t` before restarting.
