param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [string]$User = "root",
    [string]$WorkspaceDir = "$env:USERPROFILE\Documents\CodingProjects",
    [string]$FluiddPath = "",
    [string]$RepoUrl = "https://github.com/fluidd-core/fluidd.git",
    [string]$RepoRef = "v1.36.4",
    [switch]$ApplyCfsPatch = $true,
    [string]$PrebuiltAssetUrl = "https://github.com/mschoettli/CFSspoolsync/releases/download/cfs-dashboard-embed-v1/fluidd-cfs-ui-dist.tar.gz",
    [switch]$UpdateRepo,
    [string]$RemoteSourceDir = "/tmp/fluidd-new",
    [string]$RemoteDeployScript = "/tmp/deploy_fluidd_patch.sh",
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
    param([Parameter(Mandatory = $true)][string]$RepoPath)

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
    src: `${window.location.protocol}//${window.location.hostname}:4409/?view=fluidd&layout=card`,
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
    Set-Content -Path $widgetPath -Value $widgetContent -Encoding utf8

    $dashboard = Get-Content -Path $dashboardPath -Raw
    if ($dashboard -notmatch "import CfsEmbed from '@/components/widgets/CfsEmbed\.vue'") {
        $dashboard = $dashboard -replace "(import AfcCard from '@/components/widgets/afc/AfcCard\.vue'\r?\n)", "`$1import CfsEmbed from '@/components/widgets/CfsEmbed.vue'`r`n"
    }
    if ($dashboard -notmatch "(?m)^\s*CfsEmbed\s*,?\s*$") {
        $dashboard = $dashboard -replace "(AfcCard\s*,?\r?\n)", "`$1    CfsEmbed,`r`n"
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
Assert-Command -Name "tar.exe"

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
        $repoPrepared = $true

        if ($ApplyCfsPatch) {
            Write-Host "Applying CFS patch set..."
            Apply-CfsPatchToFluidd -RepoPath $resolvedFluiddPath
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
    Write-Host "Falling back to prebuilt Fluidd CFS artifact..."
    $prebuiltRoot = Join-Path -Path $WorkspaceDir -ChildPath "fluidd-cfs-prebuilt"
    $archivePath = Join-Path -Path $WorkspaceDir -ChildPath "fluidd-cfs-ui-dist.tar.gz"

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
Write-Host "  curl.exe -s ""http://$TargetHost`:7125/server/extensions/list"""
