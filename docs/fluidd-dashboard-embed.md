# Fluidd Dashboard Embed

This document describes how to show CFSspoolsync directly inside the Fluidd dashboard with a small Fluidd customization.

## Overview

Fluidd does not provide a generic built-in dashboard widget for arbitrary external SPAs.  
To render CFSspoolsync in the dashboard, use:

1. CFSspoolsync compact mode (`?view=fluidd`, optional `layout=card`)
2. A same-origin reverse proxy endpoint
3. A small Fluidd custom dashboard card (iframe)

## CFSspoolsync URL

Use one of these URLs in the embed card:

- `http://<fluidd-host>:4409/?view=fluidd`
- `http://<fluidd-host>:4409/?view=fluidd&layout=card`

`layout=card` reduces padding and improves stability in fixed-height dashboard tiles.

## Nginx Proxy (K2/Fluidd Host)

Add a dedicated server block for CFSspoolsync:

```nginx
server {
    listen 4409;

    access_log /var/log/nginx/cfs-access.log;
    error_log  /var/log/nginx/cfs-error.log;

    location / {
        proxy_pass http://<cfs-host>:8088/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://<cfs-host>:8088/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

Optional fallback from old bookmarks:

```nginx
location ^~ /cfs/ {
    return 302 http://$host:4409/?view=fluidd$is_args$args;
}
```

## Fluidd Custom Card (Fork)

Implement a small dashboard card component in your Fluidd fork:

- Card title: `CFS Slots`
- Body: iframe with the CFS compact URL
- Height: fixed card height with internal iframe fill
- Error state: show direct-link fallback if iframe cannot load

Recommended iframe attributes:

- `src="http://<fluidd-host>:4409/?view=fluidd&layout=card"`
- `style="width:100%;height:100%;border:0;"`

## Build and Deploy Workflow

1. Keep the Fluidd dashboard-card changes in a dedicated branch/fork.
2. Build Fluidd (`npm install`, `npm run build` in Fluidd repo).
3. Deploy the built assets to the Fluidd web root on the device.
4. Re-run this workflow after upstream Fluidd updates (rebase + rebuild).

## Verification Checklist

1. `http://<fluidd-host>:4408` (Fluidd) still connects to Moonraker.
2. `http://<fluidd-host>:4409/?view=fluidd` loads and updates live.
3. Dashboard card appears and renders the iframe.
4. Slot actions and modals work inside the embedded view.
5. No MIME, CSP, or websocket upgrade errors in browser console.
