param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [string]$User = "root",
    [string]$WorkspaceDir = "$env:USERPROFILE\Documents\CodingProjects",
    [string]$FluiddPath = "",
    [string]$RepoUrl = "https://github.com/fluidd-core/fluidd.git",
    [string]$RepoRef = "v1.36.4",
    [switch]$ApplyCfsPatch = $true,
    [string]$PrebuiltAssetUrl = "",
    [switch]$UpdateRepo,
    [string]$RemoteSourceDir = "/tmp/fluidd-new",
    [string]$RemoteDeployScript = "/tmp/deploy_fluidd_patch.sh",
    [string]$CfsHost = "",
    [int]$CfsPort = 8088,
    [int]$ProxyPort = 4409,
    [switch]$ConfigureProxy,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

function Assert-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

function Resolve-DistPath {
    param([Parameter(Mandatory = $true)][string]$RootPath)

    $root = (Resolve-Path -Path $RootPath).Path
    $directIndex = Join-Path -Path $root -ChildPath "index.html"
    $directAssets = Join-Path -Path $root -ChildPath "assets"
    $nestedDist = Join-Path -Path $root -ChildPath "dist"
    $nestedIndex = Join-Path -Path $nestedDist -ChildPath "index.html"
    $nestedAssets = Join-Path -Path $nestedDist -ChildPath "assets"

    if ((Test-Path -Path $directIndex -PathType Leaf) -and (Test-Path -Path $directAssets -PathType Container)) {
        return $root
    }
    if ((Test-Path -Path $nestedIndex -PathType Leaf) -and (Test-Path -Path $nestedAssets -PathType Container)) {
        return $nestedDist
    }
    return $null
}

function Apply-CfsPatchToFluidd {
    param(
        [Parameter(Mandatory = $true)][string]$RepoPath,
        [Parameter(Mandatory = $true)][int]$EmbedPort
    )

    $widgetDir = Join-Path -Path $RepoPath -ChildPath "src/components/widgets"
    $widgetPath = Join-Path -Path $widgetDir -ChildPath "CfsEmbed.vue"
    $dashboardPath = Join-Path -Path $RepoPath -ChildPath "src/views/Dashboard.vue"
    $layoutStatePath = Join-Path -Path $RepoPath -ChildPath "src/store/layout/state.ts"

    if (-not (Test-Path -Path $widgetDir -PathType Container)) {
        throw "Widget directory not found: $widgetDir"
    }
    if (-not (Test-Path -Path $dashboardPath -PathType Leaf)) {
        throw "Dashboard file not found: $dashboardPath"
    }
    if (-not (Test-Path -Path $layoutStatePath -PathType Leaf)) {
        throw "Layout state file not found: $layoutStatePath"
    }

    $widgetContent = @'
<template>
  <v-card class="fill-height cfs-embed-card">
    <v-card-title class="py-2">CFS Slots</v-card-title>
    <v-card-text class="pa-0 cfs-embed-body">
      <iframe
        :src="src"
        class="cfs-embed-frame"
        loading="lazy"
      />
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'CfsEmbed',
  data: () => ({
    src: `${window.location.protocol}//${window.location.hostname}:EMBED_PORT/?view=fluidd&layout=card`,
  }),
})
</script>

<style scoped>
.cfs-embed-card {
  min-height: 760px;
}

.cfs-embed-body {
  height: calc(760px - 48px);
}

.cfs-embed-frame {
  width: 100%;
  height: 100%;
  border: 0;
}
</style>
'@
    $widgetContent = $widgetContent.Replace("EMBED_PORT", $EmbedPort.ToString())
    Set-Content -Path $widgetPath -Value $widgetContent -Encoding utf8

    $dashboard = Get-Content -Path $dashboardPath -Raw
    if ($dashboard -notmatch "import CfsEmbed from '@/components/widgets/CfsEmbed\.vue'") {
        $dashboard = $dashboard -replace "(import AfcCard from '@/components/widgets/afc/AfcCard\.vue'\r?\n)", "`$1import CfsEmbed from '@/components/widgets/CfsEmbed.vue'`r`n"
    }
    if ($dashboard -notmatch "(?m)^\s*CfsEmbed\s*,?\s*$") {
        # Ensure AfcCard has a comma, then append CfsEmbed on the next line.
        $dashboard = $dashboard -replace "(?m)^(\s*AfcCard)\s*$", "`$1,"
        $dashboard = $dashboard -replace "(?m)^(\s*AfcCard,)\s*$", "`$1`r`n    CfsEmbed,"
    }
    Set-Content -Path $dashboardPath -Value $dashboard -Encoding utf8

    $layoutState = Get-Content -Path $layoutStatePath -Raw
    if ($layoutState -notmatch "id:\s*'cfs-embed'") {
        $layoutState = $layoutState -replace "(container1:\s*\[\r?\n)", "`$1      { id: 'cfs-embed', enabled: true },`r`n"
    }
    Set-Content -Path $layoutStatePath -Value $layoutState -Encoding utf8
}

Assert-Command -Name "scp.exe"
Assert-Command -Name "ssh.exe"
Assert-Command -Name "npm.cmd"
Assert-Command -Name "git.exe"

$localDeployScript = Join-Path -Path $PSScriptRoot -ChildPath "deploy_fluidd_patch.sh"

if (-not (Test-Path -Path $localDeployScript -PathType Leaf)) {
    throw "Local deploy helper not found: $localDeployScript"
}

if ([string]::IsNullOrWhiteSpace($FluiddPath)) {
    $FluiddPath = Join-Path -Path $WorkspaceDir -ChildPath "fluidd-cfs-auto"
}

if (-not (Test-Path -Path $WorkspaceDir -PathType Container)) {
    New-Item -ItemType Directory -Path $WorkspaceDir | Out-Null
}

$distPath = $null
$repoPrepared = $false

try {
    $fluiddRepoExists = Test-Path -Path (Join-Path $FluiddPath ".git") -PathType Container
    if (-not $fluiddRepoExists) {
        Write-Host "Cloning Fluidd repo: $RepoUrl"
        Invoke-Checked -FilePath "git.exe" -Arguments @("clone", $RepoUrl, $FluiddPath)
    }

    $resolvedFluiddPath = (Resolve-Path -Path $FluiddPath).Path
    Write-Host "Checking out ref: $RepoRef"
    Push-Location $resolvedFluiddPath
    try {
        if ($UpdateRepo) {
            Invoke-Checked -FilePath "git.exe" -Arguments @("fetch", "--all", "--tags", "--prune")
        }
        Invoke-Checked -FilePath "git.exe" -Arguments @("checkout", $RepoRef)
        Invoke-Checked -FilePath "git.exe" -Arguments @("reset", "--hard", "HEAD")
        Invoke-Checked -FilePath "git.exe" -Arguments @("clean", "-fd")
        $repoPrepared = $true

        if ($ApplyCfsPatch) {
            Write-Host "Applying CFS patch set..."
            Apply-CfsPatchToFluidd -RepoPath $resolvedFluiddPath -EmbedPort $ProxyPort
        }
    }
    finally {
        Pop-Location
    }

    if (-not $SkipBuild) {
        Write-Host "Building patched Fluidd at: $resolvedFluiddPath"
        Push-Location $resolvedFluiddPath
        try {
            Invoke-Checked -FilePath "npm.cmd" -Arguments @("ci")
            Invoke-Checked -FilePath "npm.cmd" -Arguments @("run", "build")
        }
        finally {
            Pop-Location
        }
    }
    else {
        Write-Host "Skipping build step."
    }

    $distPath = Resolve-DistPath -RootPath $resolvedFluiddPath
}
catch {
    Write-Warning "Repo build path failed: $($_.Exception.Message)"
}

if (-not $distPath) {
    if ([string]::IsNullOrWhiteSpace($PrebuiltAssetUrl)) {
        throw "Build failed and no prebuilt fallback URL is configured. Fix build errors or pass -PrebuiltAssetUrl <url>."
    }

    Assert-Command -Name "tar.exe"
    Write-Host "Falling back to prebuilt Fluidd CFS artifact..."
    $prebuiltRoot = Join-Path -Path $WorkspaceDir -ChildPath "fluidd-cfs-prebuilt"
    $archivePath = Join-Path -Path $WorkspaceDir -ChildPath "fluidd-cfs-ui-dist.tar.gz"

    try {
        if (Test-Path -Path $prebuiltRoot) {
            Remove-Item -Recurse -Force $prebuiltRoot
        }
        New-Item -ItemType Directory -Path $prebuiltRoot | Out-Null

        Invoke-WebRequest -Uri $PrebuiltAssetUrl -OutFile $archivePath
        Invoke-Checked -FilePath "tar.exe" -Arguments @("-xzf", $archivePath, "-C", $prebuiltRoot)

        $distPath = Resolve-DistPath -RootPath $prebuiltRoot
        if (-not $distPath) {
            throw "Prebuilt artifact does not contain a valid dist structure."
        }
    }
    catch {
        throw "Fallback download/extract failed ($PrebuiltAssetUrl). Original build error path also failed."
    }
}

$remote = "$User@$TargetHost"

Write-Host "Preparing remote temp dir: $RemoteSourceDir"
Invoke-Checked -FilePath "ssh.exe" -Arguments @($remote, "rm -rf $RemoteSourceDir && mkdir -p $RemoteSourceDir")

Write-Host "Uploading dist folder..."
Invoke-Checked -FilePath "scp.exe" -Arguments @("-r", $distPath, "$remote`:$RemoteSourceDir")

Write-Host "Uploading deploy helper..."
Invoke-Checked -FilePath "scp.exe" -Arguments @($localDeployScript, "$remote`:$RemoteDeployScript")

Write-Host "Running remote deploy..."
Invoke-Checked -FilePath "ssh.exe" -Arguments @(
    $remote,
    "chmod +x $RemoteDeployScript && $RemoteDeployScript $RemoteSourceDir/dist"
)

if ($ConfigureProxy) {
    if ([string]::IsNullOrWhiteSpace($CfsHost)) {
        throw "When -ConfigureProxy is used, -CfsHost is required."
    }

    $proxySetupScriptPath = Join-Path -Path $env:TEMP -ChildPath "cfs_proxy_setup.sh"
    $proxySetupScript = @'
#!/bin/sh
set -eu

NGINX_CONF="/etc/nginx/nginx.conf"
TMP_BASE="/tmp/nginx_conf_cfs_proxy"
TMP_CLEAN="${TMP_BASE}.clean"
TMP_NEW="${TMP_BASE}.new"
BLOCK_FILE="${TMP_BASE}.block"

cat > "$BLOCK_FILE" <<'EOF'
    # >>> CFS_PROXY_AUTOGEN >>>
    server {
        listen PROXY_PORT;
        server_name _;

        location / {
            proxy_pass http://CFS_HOST:CFS_PORT/;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /ws {
            proxy_pass http://CFS_HOST:CFS_PORT/ws;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
        }
    }
    # <<< CFS_PROXY_AUTOGEN <<<
EOF

sed -i "s/PROXY_PORT/PROXY_PORT_VALUE/g; s/CFS_HOST/CFS_HOST_VALUE/g; s/CFS_PORT/CFS_PORT_VALUE/g" "$BLOCK_FILE"

awk '
BEGIN { skip=0 }
/# >>> CFS_PROXY_AUTOGEN >>>/ { skip=1; next }
/# <<< CFS_PROXY_AUTOGEN <<</ { skip=0; next }
skip==0 { print }
' "$NGINX_CONF" > "$TMP_CLEAN"

awk -v blockfile="$BLOCK_FILE" '
{ lines[NR] = $0 }
END {
  last = 0
  for (i = NR; i >= 1; i--) {
    if (lines[i] ~ /^[[:space:]]*}[[:space:]]*$/) {
      last = i
      break
    }
  }
  if (last == 0) {
    for (i = 1; i <= NR; i++) print lines[i]
    exit 1
  }
  for (i = 1; i < last; i++) print lines[i]
  while ((getline line < blockfile) > 0) print line
  close(blockfile)
  for (i = last; i <= NR; i++) print lines[i]
}
' "$TMP_CLEAN" > "$TMP_NEW"

cp "$NGINX_CONF" "$NGINX_CONF.bak.$(date +%Y%m%d-%H%M%S)"
mv "$TMP_NEW" "$NGINX_CONF"
rm -f "$TMP_CLEAN" "$BLOCK_FILE"

nginx -t
nginx -s reload
'@
    $proxySetupScript = $proxySetupScript.Replace("PROXY_PORT_VALUE", $ProxyPort.ToString())
    $proxySetupScript = $proxySetupScript.Replace("CFS_HOST_VALUE", $CfsHost)
    $proxySetupScript = $proxySetupScript.Replace("CFS_PORT_VALUE", $CfsPort.ToString())
    Set-Content -Path $proxySetupScriptPath -Value $proxySetupScript -Encoding ascii

    Write-Host "Configuring nginx proxy on target host ($ProxyPort -> $CfsHost`:$CfsPort)..."
    Invoke-Checked -FilePath "scp.exe" -Arguments @($proxySetupScriptPath, "$remote`:/tmp/cfs_proxy_setup.sh")
    Invoke-Checked -FilePath "ssh.exe" -Arguments @(
        $remote,
        "sed -i 's/\r$//' /tmp/cfs_proxy_setup.sh && chmod +x /tmp/cfs_proxy_setup.sh && /tmp/cfs_proxy_setup.sh"
    )
}

Write-Host ""
Write-Host "Done."
if ($repoPrepared) {
    Write-Host "Source mode: repository build"
}
else {
    Write-Host "Source mode: prebuilt artifact"
}
Write-Host "Validate from PowerShell:"
Write-Host "  curl.exe -I ""http://$TargetHost`:4408/"""
if ($ConfigureProxy) {
    Write-Host "  curl.exe -I ""http://$TargetHost`:$ProxyPort/?view=fluidd&layout=card"""
}
elseif (-not [string]::IsNullOrWhiteSpace($CfsHost)) {
    Write-Host "  curl.exe -I ""http://$CfsHost`:$CfsPort/?view=fluidd&layout=card"""
}
Write-Host "  curl.exe -s ""http://$TargetHost`:7125/server/extensions/list"""
