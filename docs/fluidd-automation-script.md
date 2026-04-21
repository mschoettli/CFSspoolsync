# Fluidd Automation Script Guide

This guide documents the single automation entrypoint for patched Fluidd deployment.

Script file:
- `scripts/build_and_deploy_fluidd_cfs.ps1`

## Purpose

The script performs a full end-to-end deployment of patched Fluidd to the target host:
1. Clone patched Fluidd repository if missing.
2. Checkout the configured ref.
3. Build with `npm ci` and `npm run build`.
4. Fallback to prebuilt release artifact if clone/build fails.
5. Upload build files to the remote host.
6. Run remote deploy helper:
   - backup current `/usr/share/fluidd`
   - replace files
   - fix ownership and permissions
   - validate and reload nginx

## Prerequisites

- Windows PowerShell.
- Local tools in `PATH`:
  - `git.exe`
  - `npm.cmd`
  - `ssh.exe`
  - `scp.exe`
  - `tar.exe`
- SSH access to the Fluidd host (default user is `root`).
- Remote host must contain nginx and writable `/usr/share/fluidd`.

## Minimal command

Run from repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_deploy_fluidd_cfs.ps1 `
  -TargetHost "192.168.0.1"
```

## Parameters

- `-TargetHost` (required)
  - Hostname or IP of Fluidd nginx host.
- `-User` (default: `root`)
  - SSH user for remote commands.
- `-WorkspaceDir` (default: `$env:USERPROFILE\Documents\CodingProjects`)
  - Parent directory for auto-managed local checkout and fallback files.
- `-FluiddPath` (default: `<WorkspaceDir>\fluidd-cfs-auto`)
  - Local checkout path.
- `-RepoUrl` (default: `https://github.com/mschoettli/fluidd.git`)
  - Patched Fluidd repository URL.
- `-RepoRef` (default: `cfs-dashboard-embed-v1`)
  - Branch, tag, or commit to deploy.
- `-PrebuiltAssetUrl` (default: CFSspoolsync release artifact for `cfs-dashboard-embed-v1`)
  - Download URL used when repository clone/build path is unavailable.
- `-UpdateRepo` (switch)
  - Runs `git fetch --all --tags --prune` before checkout.
- `-SkipBuild` (switch)
  - Skips local npm build and deploys existing `dist`.
- `-RemoteSourceDir` (default: `/tmp/fluidd-new`)
  - Temporary upload path on host.
- `-RemoteDeployScript` (default: `/tmp/deploy_fluidd_patch.sh`)
  - Remote path for deploy helper script.

## Common variants

Update repository before checkout:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_deploy_fluidd_cfs.ps1 `
  -TargetHost "192.168.0.1" `
  -UpdateRepo
```

Deploy existing `dist` without running npm build:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_deploy_fluidd_cfs.ps1 `
  -TargetHost "192.168.0.1" `
  -SkipBuild
```

## Validation

From Windows PowerShell:

```powershell
curl.exe -I "http://192.168.0.1:4408/"
curl.exe -s "http://192.168.0.1:7125/server/extensions/list"
```

Expected:
- Fluidd root returns `200 OK`.
- `cfssync` appears in Moonraker extension agents (if agent is enabled).
