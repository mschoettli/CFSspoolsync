# Fluidd Dashboard Integration for End Users

This guide shows how to integrate CFSspoolsync into the Fluidd dashboard as an interactive card.

Use this as a copy/paste workflow for:
- K2/OpenWrt hosts
- Generic Linux hosts

Important:
- All example IPs use `192.168.0.1` placeholders.
- Replace each placeholder with your own host IP before running commands.
- The dashboard integration uses a small Fluidd fork/custom build.

## If This Is Too Complex

If this setup feels too complex, use an AI assistant to guide you step by step on your exact host.

Recommended approach:
1. Share your current Nginx config and Fluidd/CFS host IPs.
2. Ask the assistant to generate a complete, host-specific command sequence.
3. Run each command one by one and verify after each step (`nginx -t`, `curl -I` checks).
4. If an error appears, paste the exact error output and continue iteratively.

Safety note:
- Never run commands you do not understand.
- Always create a backup of `/usr/share/fluidd` and your Nginx config before changes.

## Prerequisites

- CFSspoolsync is running and reachable:
  - `http://192.168.0.1:8088`
- Fluidd host is reachable:
  - `http://192.168.0.1:4408`
- SSH access to the Fluidd host.
- A Fluidd fork that includes the CFS dashboard card.

## Release Pinning (Recommended)

Use one stable Fluidd fork revision for reproducible installs.

- Known-good Fluidd upstream version: `1.36.4`
- Recommended release tag in your fork: `cfs-dashboard-embed-v1`
- Recommended documentation field in your fork release notes:
  - `Known-good commit SHA: <your-fork-commit-sha>`

If you publish prebuilt assets, provide them as release artifacts for the same tag.

## Step 1: Add CFS Reverse Proxy on Port 4409

Add this server block to your Nginx config on the Fluidd host:

```nginx
server {
    listen 4409;

    access_log /var/log/nginx/cfs-access.log;
    error_log  /var/log/nginx/cfs-error.log;

    location / {
        proxy_pass http://192.168.0.1:8088/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://192.168.0.1:8088/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

Apply and reload:

```bash
nginx -t
nginx -s reload
```

## Step 2: Build Fluidd Fork

The card should embed:
- `http://<fluidd-host>:4409/?view=fluidd&layout=card`

The minimal fork changes are:
- `src/components/widgets/CfsEmbed.vue`
- `src/views/Dashboard.vue` (import and component registration)
- layout state with card ID `cfs-embed`

Minimal snippets:

`src/components/widgets/CfsEmbed.vue`:

```vue
<template>
  <v-card class="fill-height cfs-embed-card">
    <v-card-title class="py-2">CFS Slots</v-card-title>
    <v-card-text class="pa-0 cfs-embed-body">
      <iframe :src="src" class="cfs-embed-frame" loading="lazy" />
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'CfsEmbed',
  data: () => ({
    src: `${window.location.protocol}//${window.location.hostname}:4409/?view=fluidd&layout=card`,
  }),
})
</script>

<style scoped>
.cfs-embed-card { min-height: 760px; }
.cfs-embed-body { height: calc(760px - 48px); }
.cfs-embed-frame { width: 100%; height: 100%; border: 0; }
</style>
```

`src/views/Dashboard.vue`:

```ts
import CfsEmbed from '@/components/widgets/CfsEmbed.vue'
```

```ts
components: {
  // existing cards...
  CfsEmbed
}
```

`src/store/layout/state.ts` (or equivalent layout defaults file in your fork):

```ts
{ id: 'cfs-embed', enabled: true }
```

Build commands:

Windows PowerShell:

```powershell
cd "C:\path\to\fluidd"
npm.cmd install
npm.cmd run build
```

Linux shell:

```bash
cd /path/to/fluidd
npm install
npm run build
```

## Step 3: Deploy Build to `/usr/share/fluidd`

Copy from your workstation to host:

Windows PowerShell example:

```powershell
scp -r .\dist root@192.168.0.1:/tmp/fluidd-new
```

Linux shell example:

```bash
scp -r ./dist root@192.168.0.1:/tmp/fluidd-new
```

Deploy on host:

```bash
rm -rf /usr/share/fluidd/*
cp -a /tmp/fluidd-new/* /usr/share/fluidd/
```

Important:
- This guide uses `cp -a /tmp/fluidd-new/*`.
- Do not use `/tmp/fluidd-new/dist/*` unless that path actually exists on your host.

## Step 4: Set Permissions and Reload

```bash
chown -R root:root /usr/share/fluidd
find /usr/share/fluidd -type d -exec chmod 755 {} \;
find /usr/share/fluidd -type f -exec chmod 644 {} \;
nginx -t
nginx -s reload
```

## Optional: One-Command Windows Automation

Use the helper script in this repo to clone/update patched Fluidd, build it, and deploy automatically.

From this repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_deploy_fluidd_cfs.ps1 `
  -TargetHost "192.168.0.1"
```

What it does:
1. Clones patched Fluidd from `https://github.com/mschoettli/fluidd.git` (if missing).
2. Checks out `cfs-dashboard-embed-v1`.
3. Runs `npm ci` and `npm run build`.
4. Uploads `dist` to the host under `/tmp/fluidd-new/dist`.
5. Uploads and runs `scripts/deploy_fluidd_patch.sh`.
6. Deploys to `/usr/share/fluidd`, fixes permissions, and reloads Nginx.

Optional:
- Force refresh repo before checkout:
  - add `-UpdateRepo`
- Use custom local checkout path:
  - add `-FluiddPath "C:\path\to\patched-fluidd"`
- Use custom branch/tag:
  - add `-RepoRef "your-branch-or-tag"`

If you already built `dist`, skip build:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_deploy_fluidd_cfs.ps1 `
  -TargetHost "192.168.0.1" `
  -SkipBuild
```

## Step 5: Enable the Dashboard Card

Open Fluidd:
- `http://192.168.0.1:4408`

Then:
1. Open Dashboard layout/edit mode.
2. Add or enable `CFS Slots`.
3. Save layout.

## After Docker Re-Deploy (What to Repeat)

If you only re-deploy CFSspoolsync containers, you usually do not need to rebuild Fluidd.

Repeat only these checks:
1. Verify CFS is reachable:
   - `http://192.168.0.1:8088/?view=fluidd&layout=card`
2. Verify Fluidd proxy endpoint still works:
   - `http://192.168.0.1:4409/?view=fluidd&layout=card`
3. Open Fluidd dashboard and confirm the `CFS Slots` card is updating.

Rebuild/redeploy Fluidd only if:
- `/usr/share/fluidd` was overwritten by firmware/update.
- Your Fluidd fork changed.
- The dashboard card is missing after update.

If rebuild is required, repeat:
- Step 2 (Build Fluidd fork)
- Step 3 (Deploy to `/usr/share/fluidd`)
- Step 4 (Permissions + reload)

## Validation Commands

Use these checks after deployment.

Root page:

```bash
curl -I http://192.168.0.1:4408/
```

Expected:
- `HTTP/1.1 200 OK`

Assets:
1. Find actual hashed asset name from HTML source.
2. Validate one existing JS asset:

```bash
curl -I http://192.168.0.1:4408/assets/<actual-hash>.js
```

Expected:
- `HTTP/1.1 200 OK`
- JavaScript MIME type

## Recovery (Common Problems)

### 403 for `/` or 500 for `/favicon.ico`

Usually permissions or missing files under `/usr/share/fluidd`.

Check:

```bash
ls -lah /usr/share/fluidd
ls -lah /usr/share/fluidd/assets
```

Fix:

```bash
chown -R root:root /usr/share/fluidd
find /usr/share/fluidd -type d -exec chmod 755 {} \;
find /usr/share/fluidd -type f -exec chmod 644 {} \;
nginx -t && nginx -s reload
```

### MIME errors (`text/html` for JS modules)

Usually stale hashed asset URLs from browser cache/service worker.

Fix:
1. Unregister service worker in browser dev tools.
2. Clear site data.
3. Hard refresh (`Ctrl+F5`).
4. Re-test `curl -I /assets/<actual>.js`.

### Empty `/usr/share/fluidd`

This causes `403` and redirect cycles.

Fix:
1. Copy build files again to `/tmp/fluidd-new`.
2. Deploy with:
   - `cp -a /tmp/fluidd-new/* /usr/share/fluidd/`
3. Reapply ownership/permissions.

## Related Docs

- [Fluidd Dashboard Embed (technical)](fluidd-dashboard-embed.md)
- [Troubleshooting Guide](troubleshooting.md)

## Remove Fluidd UI Integration (Keep Moonraker Agent)

Use this when you want to remove the Fluidd dashboard card/custom web patch, but keep API integration through Moonraker extensions.

### 1) Remove card from dashboard layout

In Fluidd:
1. Open `Dashboard`.
2. Enter `Layout/Edit` mode.
3. Remove `CFS Slots`.
4. Save layout.

### 2) Restore original Fluidd web root

On the Fluidd host:

```bash
ls -1dt /root/fluidd-backup-* | head -n 5
```

Pick one timestamp and restore it:

```bash
rm -rf /usr/share/fluidd/*
cp -a /root/fluidd-backup-<your-timestamp>/. /usr/share/fluidd/
chown -R root:root /usr/share/fluidd
find /usr/share/fluidd -type d -exec chmod 755 {} \;
find /usr/share/fluidd -type f -exec chmod 644 {} \;
nginx -t
nginx -s reload
```

Important:
- Replace `<your-timestamp>` with a real folder name from `ls -1dt`.
- Do not copy the literal placeholder string.

### 3) Optional: remove CFS UI proxy on `:4409`

If you do not want iframe UI embed anymore:
1. Edit Nginx config.
2. Remove the `server { listen 4409; ... }` block.
3. Reload:

```bash
nginx -t
nginx -s reload
```

### 4) Optional: remove temporary UI deployment artifacts

```bash
rm -rf /tmp/fluidd-new
rm -f /tmp/fluidd-cfs-ui.tar.gz
```

### 5) Validation

From PowerShell:

```powershell
curl.exe -I "http://192.168.0.1:4408/"
```

Expected:
- `HTTP/1.1 200 OK`
- No `CFS Slots` card in dashboard.

If you removed `:4409`, this should fail/not respond:
- `http://192.168.0.1:4409`

Agent still active check:

```powershell
curl.exe -s "http://192.168.0.1:7125/server/extensions/list"
```

Expected:
- `cfssync` still listed in `agents`.
