---
name: cf-pages-deploy
description: "Host a static site at <name>.cosmicfarmland.wtf on Cloudflare Pages (free, no Railway): repo, Pages project from GitHub, custom domain, CNAME, live verify. Triggers: /cf-pages-deploy <name>, 'put it on Pages', 'static site to cloudflare'. Use /cf-deploy for anything with a server."
---

# cf-pages-deploy <name>

One pass, no questions. `<name>` = subdomain and repo name. Idempotent re-run is fine. Static output only; a server process means `/cf-deploy` instead.

Precondition (one-time): the "Cloudflare Workers and Pages" GitHub app is installed on marshallhouston with **All repositories**. If a new repo is not visible to Pages, that setting slipped back to "selected repos": fix at https://github.com/settings/installations.

## Steps

1. **Build script.** `package.json` needs a `build` script that writes `dist/`. Static files with no build tool: `"build": "rm -rf dist && mkdir dist && cp -r <files> dist/"`. Add `dist/` to `.gitignore`. Commit.
2. **Repo.** If cwd has no origin: `gh repo create marshallhouston/<name> --private --source=. --push`. Else push.
3. **Pages project.** `mcp__cloudflare__execute` (account is pre-set):
   ```js
   async () => cloudflare.request({ method: "POST", path: `/accounts/${accountId}/pages/projects`, body: {
     name: "<name>", production_branch: "main",
     source: { type: "github", config: { owner: "marshallhouston", repo_name: "<name>", production_branch: "main",
       pr_comments_enabled: false, deployments_enabled: true, production_deployments_enabled: true, preview_deployment_setting: "none" } },
     build_config: { build_command: "npm run build", destination_dir: "dist", root_dir: "" },
     deployment_configs: { production: {}, preview: {} } } })
   ```
   Error 8000011 = GitHub app cannot see the repo (see precondition). Do not create the project without `source`: a Direct Upload project can never be switched to Git (error 8000069), only deleted and recreated.
4. **Custom domain.** `POST /accounts/${accountId}/pages/projects/<name>/domains` body `{ name: "<name>.cosmicfarmland.wtf" }`.
5. **CNAME.** Zone `118c233a5043aa105be592249c7c608b`. Same MCP: `POST /zones/<zone>/dns_records` `{ type: "CNAME", name: "<name>", content: "<name>.pages.dev", proxied: true }`. If the record exists (migrating off Railway), GET by name then PATCH. Proxied is fine for Pages.
6. **First deploy.** Creating the project triggers a build. Poll `GET .../pages/projects/<name>/deployments` until `latest_stage.name == "deploy"` and `status == "success"`, or curl `https://<name>.pages.dev` until 200.
7. **Verify.** `curl -sI https://<name>.cosmicfarmland.wtf/` must be 200 **and** carry Pages fingerprints (`etag` is a 32-hex md5, headers include `x-content-type-options: nosniff` and `access-control-allow-origin: *`, no `x-railway-*`). Status code alone is not proof when a proxied CNAME previously pointed at Railway. Report the URL only after this passes. The Pages domain `status` may sit at `pending` after traffic already works; ignore it.
8. **Migrating off Railway?** Only after step 7: `mcp__railway__delete-service`, then remove the Dockerfile / `railway.json` from the repo. The empty Railway project has no delete tool; dashboard.

## Notes
- No API token, no CI workflow, no wrangler: Pages builds from GitHub itself. The keychain `cloudflare-api-token` is DNS-only and cannot touch Pages; use the Cloudflare MCP.
- Pages build image runs `npm run build` with Node; keep the build script npm-compatible even in bun repos.
