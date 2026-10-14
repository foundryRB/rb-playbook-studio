# Install or refresh the playbook's skills and agents on this machine, served by
# playbook-studio. Downloads the bundle once and runs the playbook's own installer
# inside it (scripts/install_playbook.py), which writes what differs and prints one
# summary table. Arguments pass through to it: --prune, --runtime-dir <dir>, and the
# agents-directory option of each harness (--agents-dir, --opencode-agents-dir).
# The bundle URL carries a short-lived, download-only token. Runs as a script block,
# so a failure throws rather than exiting the caller's session. Native commands are
# judged by their exit codes, never by what they write to stderr: Windows PowerShell
# turns redirected native stderr into errors, and the Store's python3 stub writes there.
$ErrorActionPreference = 'Continue'
$PSNativeCommandUseErrorActionPreference = $false
$ProgressPreference = 'SilentlyContinue'

$bundleUrl = '__BUNDLE_URL__'

$python = $null
foreach ($candidate in @('python3', 'python', 'py')) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        & $candidate -c 'import sys; sys.exit(sys.version_info < (3, 8))' 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $python = $candidate; break }
    }
}
if (-not $python) {
    throw 'playbook install: needs Python 3.8 or newer on PATH (python, python3, or py)'
}

$work = Join-Path ([IO.Path]::GetTempPath()) ([IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Path $work -ErrorAction Stop | Out-Null
try {
    $archive = Join-Path $work 'bundle.tar.gz'
    Invoke-WebRequest -Uri $bundleUrl -OutFile $archive -UseBasicParsing -ErrorAction Stop
    $bundle = Join-Path $work 'bundle'
    New-Item -ItemType Directory -Path $bundle -ErrorAction Stop | Out-Null
    tar -xzf $archive -C $bundle
    if ($LASTEXITCODE -ne 0) { throw 'playbook install: could not unpack the bundle' }
    & $python (Join-Path (Join-Path $bundle 'scripts') 'install_playbook.py') @args
    if ($LASTEXITCODE -ne 0) { throw "playbook install: the installer exited with $LASTEXITCODE" }
}
finally {
    Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}
