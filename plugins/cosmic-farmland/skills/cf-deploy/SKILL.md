---
name: cf-deploy
description: "Provision <name>.cosmicfarmland.wtf end to end: private GitHub repo, Railway service linked with auto-deploy on push, Railway domain, Cloudflare CNAME, live verification. Triggers: /cf-deploy <name>, 'deploy it to X.cosmicfarmland.wtf', 'do the whole linking thing on railway and cloudflare'."
---

# cf-deploy <name>

One pass, no questions. `<name>` = subdomain and repo name (dashes ok). Skip any step already done (idempotent re-run is fine).

## Steps

1. **Repo.** If cwd has no origin: `gh repo create marshallhouston/<name> --private --source=. --push`. Else confirm origin matches and push.
2. **Railway project + service.** `mcp__railway__create_project` (name `<name>`) if none, then `mcp__railway__create_service` with the GitHub repo as source (`connect_service_source` links repo, auto-deploy on push is Railway default for repo-linked services; verify with `get_service_config`). Always pass explicit project_id/service_id.
3. **Railway domain.** `mcp__railway__generate_domain` for the service. Note the `*.up.railway.app` target.
4. **Custom domain on Railway.** Add `<name>.cosmicfarmland.wtf` via `mcp__railway__update_domain`/create custom domain tool; Railway returns the CNAME target.
5. **Cloudflare CNAME.** Zone `cosmicfarmland.wtf` = `118c233a5043aa105be592249c7c608b`. Token: `security find-generic-password -s cloudflare-api-token -w` (never print it).
   ```bash
   TOKEN=$(security find-generic-password -s cloudflare-api-token -w) && curl -s -X POST \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     "https://api.cloudflare.com/client/v4/zones/118c233a5043aa105be592249c7c608b/dns_records" \
     -d "{\"type\":\"CNAME\",\"name\":\"<name>\",\"content\":\"<railway-cname-target>\",\"proxied\":false}"
   ```
   If the record exists, PATCH it instead (GET dns_records?name=... first).
6. **Cert + verify.** Poll `mcp__railway__domain_status` until cert issued, then `curl -sI https://<name>.cosmicfarmland.wtf` and require HTTP 200/3xx BEFORE reporting live. Report the URL only after this passes.

## Notes
- proxied=false initially so Railway can issue the cert; flip to proxied later only if needed.
- If `railway whoami` fails, ask marshall to run `! railway login` first.
