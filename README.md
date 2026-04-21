
<a href="https://www.buymeacoffee.com/mschoettli" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-green.png" alt="Buy Me a Coffee" style="height: 50px !important;width: 197px !important;" ></a>

# CFSspoolsync

CFSspoolsync is a web app for tracking Creality K2 Combo CFS slots, spool inventory, and filament consumption with live updates.

## Current Feature Set

- Live CFS environment data: temperature, humidity, connection status
- Four slot panels with:
  - Assigned spool details
  - Remaining weight derived from live CFS data
  - Automatic print-state display (Moonraker-driven, no manual print button)
- Inventory management:
  - Create, edit, delete spools
  - Assign/unassign to slots
  - Color name and HEX synchronization (`color` or `color_hex`)
- Tare management modal:
  - Community defaults + custom entries
  - Inline editing and dedicated add-entry modal
- History modal (24h / 7d / 30d) based on backend history records
- Settings modal:
  - Language dropdown (DE, EN, FR, IT, ES, PT, NL, PL)
  - Theme toggle (dark/light)
  - Quick access to tare management
- OCR spool label scan:
  - Tesseract-based extraction
  - Optional OpenAI/Anthropic post-processing fallback (server-side only)


<img width="1585" height="223" alt="status" src="https://github.com/user-attachments/assets/c88ab44b-299d-461e-a27c-d7383f603401" />
<img width="1573" height="369" alt="slots" src="https://github.com/user-attachments/assets/6641c32b-4ee3-45ec-8382-47f9d401f881" />


## Installation

```bash
git clone https://github.com/mschoettli/CFSspoolsync.git
cd CFSspoolsync
cp .env.example .env
# Edit .env (required)
docker compose up -d
```

Open:
- `http://<host>:8088` (or your configured `HTTP_PORT`)

## Moonraker Agent Integration (Primary)

The primary integration path is the built-in Moonraker extension agent:
- [Moonraker Agent Integration Guide](docs/moonraker-agent-integration.md)

This avoids a mandatory Fluidd fork and exposes CFS methods through Moonraker extensions.

## Fluidd Embed Mode (Optional)

Use the existing app with the query parameter:
- `http://<host>:8088/?view=fluidd`

Behavior in this mode:
- Renders only the 4 slot panels (slot 1-4), including empty slots
- Hides header, KPI cards, inventory section, and footer
- Keeps slot actions and related modals available

If embedded in an iframe, ensure your reverse proxy does not block framing via
`X-Frame-Options` or restrictive `Content-Security-Policy` `frame-ancestors` rules.

## Fluidd Dashboard Integration (Automated Script)

Use the Windows automation script to set up patched Fluidd without manual copy/paste deployment steps.

Script:
- `scripts/build_and_deploy_fluidd_cfs.ps1`

What the script does:
1. Clones the patched Fluidd repository if it is missing.
2. Checks out a fixed ref (`cfs-dashboard-embed-v1` by default).
3. Builds Fluidd (`npm ci`, `npm run build`).
4. If clone/build is not possible, it automatically falls back to the prebuilt release artifact.
5. Uploads `dist` to the target host.
6. Runs the remote deploy helper to:
   - backup current `/usr/share/fluidd`
   - replace files with the new build
   - fix ownership/permissions
   - validate and reload nginx

### Prerequisites

- Windows PowerShell.
- Local tools in `PATH`: `git.exe`, `npm.cmd`, `ssh.exe`, `scp.exe`.
- SSH access to the Fluidd host as a user with permission to write `/usr/share/fluidd` and reload nginx (default: `root`).
- CFS reverse proxy on port `4409` already configured on the Fluidd host (if you use the embedded card iframe).

### One-command usage

Run from the CFSspoolsync repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_deploy_fluidd_cfs.ps1 `
  -TargetHost "192.168.0.1"
```

### Parameters (exact behavior)

- `-TargetHost` (required):
  - Hostname or IP of the Fluidd/nginx machine.
- `-User` (default: `root`):
  - SSH user used for upload and remote deploy commands.
- `-WorkspaceDir` (default: `$env:USERPROFILE\Documents\CodingProjects`):
  - Local parent directory where auto-cloned patched Fluidd is stored.
- `-FluiddPath` (default: `<WorkspaceDir>\fluidd-cfs-auto`):
  - Local patched Fluidd checkout path. If missing, the repo is cloned automatically.
- `-RepoUrl` (default: `https://github.com/mschoettli/fluidd.git`):
  - Patched Fluidd repository URL.
- `-RepoRef` (default: `cfs-dashboard-embed-v1`):
  - Git branch/tag/commit to checkout before build.
- `-PrebuiltAssetUrl`:
  - Release artifact URL used as automatic fallback when repo clone/build fails.
- `-UpdateRepo` (switch):
  - Runs `git fetch --all --tags --prune` before checkout.
- `-SkipBuild` (switch):
  - Skips `npm` build steps and deploys existing local `dist`.
- `-RemoteSourceDir` (default: `/tmp/fluidd-new`):
  - Temporary upload location on target host.
- `-RemoteDeployScript` (default: `/tmp/deploy_fluidd_patch.sh`):
  - Remote path of the deploy helper script.

### Typical variants

Refresh remote build from latest ref:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_deploy_fluidd_cfs.ps1 `
  -TargetHost "192.168.0.1" `
  -UpdateRepo
```

Deploy an already built checkout:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_deploy_fluidd_cfs.ps1 `
  -TargetHost "192.168.0.1" `
  -SkipBuild
```

## RFID / NFC Tags for CFS

The Creality CFS reads NFC/RFID spool tags and exposes their data (for example detected spool metadata and remaining amount) to the app through Moonraker/telemetry.

Example blank tags that are commonly used for this workflow:
- [LIBO MIFARE Classic 1K NFC stickers (Amazon)](https://www.amazon.de/LIBO-Aufkleber-User-Speicher-13-56-MHz-Etiketten/dp/B07GH1P2M5/ref=sr_1_6?crid=24Y6MFAB07ZIP&dib=eyJ2IjoiMSJ9.-NJBo1kDAziTJoMNN8xtEfHqZlpzphiFBT78Ax37lsSXHdemKOrkV6v5rwnzBfVZPziHWGHOoZ7rGwMyLq1JDzGdjnyQUTooVLx4T2Jx9KjwLvQOvYhhUg5skOZdjP-J8Ea0H0uzkz_KXOiNIn97uIVvSsRX7Q0JZF2yK5nrbPujZC5spCLYBe1Hbilq06C4X4-53AZTywFw2ODvsDreoxIOU00OJiswp1ziTzM_nGubOFiSNxwGXqrExABTNTHogKadDRkp7kFHJB0FgMuQaxcFaEj-oRv-rfbigFMe2t4.cbvx52elbp9MMCgagz5Csha3Wda0wBh3BOYP5mB9TYA&dib_tag=se&keywords=mifare+classic+1k&qid=1776605611&sprefix=%2Caps%2C284&sr=8-6)

### Writing tags (practical approach)

Recommended app:
- [RFID for CFS (Android, Google Play)](https://play.google.com/store/apps/details?id=com.lot38designs.cfsrfid&pli=1)

1. Use an NFC-capable Android phone (or a USB NFC writer such as ACR122U).
2. Read a known working CFS spool tag and save a dump.
3. Write that dump to a blank MIFARE Classic 1K tag.
4. Attach the new tag to the spool and trigger a slot re-read on the K2 CFS screen.

Notes:
- The exact CFS data layout is vendor-specific; cloning a known-good tag is usually the most reliable method.
- Use this only for your own hardware/media and local workflow testing.

## Documentation

- [Technical Reference](docs/technical-reference.md)
- [Development Guide](docs/development.md)
- [Moonraker Agent Integration Guide](docs/moonraker-agent-integration.md)
- [Fluidd User Integration Guide](docs/fluidd-user-integration.md)
- [Troubleshooting Guide](docs/troubleshooting.md)

## License

GNU GPL v3.0. See [LICENSE](LICENSE).
