#requires -Version 5.1
<#
.SYNOPSIS
    Build the FailBench release artifacts: source ZIP, git bundle, and SHA256SUMS.

.DESCRIPTION
    make_archive.ps1 creates deterministic release artifacts for the FailBench
    repository. By default they are written to <RepoRoot>\_scratch\dist:

        failbench-v<Version>.zip     source archive of the repository
        failbench-v<Version>.bundle  portable git bundle of all refs
        SHA256SUMS.txt               SHA-256 checksums of the artifacts above

    Before anything is archived the script scans every candidate file for
    high-confidence secret material: credential filenames (.env, .npmrc,
    *.pem, *.key, id_rsa*, credentials.json, secrets.*, *.pfx, *.p12, ...)
    and token-shaped content (GitHub, AWS, OpenAI, Slack, private-key blocks,
    generic api_key/secret/token assignments). If a match is found the script
    refuses to archive and exits with code 2.
    Clearly synthetic fixture values (dummy, fake, example, do-not-print,
    placeholder, and similar markers) that the offline test suite uses to prove
    redaction are reported as warnings and ignored, so the guard blocks real
    leaks without blocking the repository's own tests.

    File selection:
      * If a git repository exists at the repo root, tracked files are listed
        with 'git ls-files -z', so .gitignore is honored exactly and untracked
        files are excluded.
      * Otherwise a directory walk is used with the same exclusions.

    Always excluded: .git, _scratch, __pycache__, *.pyc, .venv, venv,
    node_modules, *.zip, and raw results (anything under results\ except
    results\demo\). The output directory is excluded from the archive if it
    lives inside the repository.

    The script is idempotent: re-running overwrites the artifacts and leaves
    no temporary files behind. It never pushes or publishes anything.

.PARAMETER RepoRoot
    Repository root to archive. Defaults to the root derived from the script
    location (two levels above scripts\publish).

.PARAMETER Version
    Release version. Must match ^\d+\.\d+\.\d+$ (for example 0.1.0).
    Defaults to 0.1.0 and is used in the artifact file names.

.PARAMETER OutDir
    Output directory for the artifacts. Defaults to <RepoRoot>\_scratch\dist.
    A relative path is resolved against the current working directory.

.PARAMETER GitPath
    Optional path to a git executable. Default resolution order:
    _scratch\Git\bin\git.exe under the repo root, then the same path under
    this script's repository root, then $env:FAILBENCH_GIT, then git from PATH.

.PARAMETER SkipBundle
    Explicitly skip git bundle creation. The source ZIP and SHA256SUMS.txt are
    still produced.

.EXAMPLE
    PS> powershell -NoProfile -ExecutionPolicy Bypass -File scripts\publish\make_archive.ps1

    Build the artifacts for the repository that contains the script.

.EXAMPLE
    PS> .\scripts\publish\make_archive.ps1 -Version 0.2.0 -SkipBundle

    Build only the source ZIP for version 0.2.0.

.EXAMPLE
    PS> .\scripts\publish\make_archive.ps1 -RepoRoot C:\work\failbench -OutDir _scratch\dist

    Archive another checkout and write the artifacts under _scratch\dist.

.EXAMPLE
    PS> .\scripts\publish\make_archive.ps1 -GitPath C:\tools\git\bin\git.exe -Verbose

    Use an explicit git executable for the bundle step.

.INPUTS
    None.

.OUTPUTS
    None. Console messages use [INFO]/[OK]/[WARN]/[ERROR] prefixes.
    Exit codes: 0 success, 1 build failure, 2 secret-like content detected.

.NOTES
    Targets PowerShell 7 and is fully Windows PowerShell 5.1 compatible.
    No external modules are required. Nothing is pushed or published.
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = '',
    [string]$Version = '0.1.0',
    [string]$OutDir = '',
    [string]$GitPath = '',
    [switch]$SkipBundle
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

function Write-ArchiveInfo {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host ('[INFO] ' + $Message)
}

function Write-ArchiveOk {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host ('[OK] ' + $Message)
}

function Write-ArchiveWarn {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host ('[WARN] ' + $Message)
}

function Write-ArchiveError {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host ('[ERROR] ' + $Message)
}

# ---------------------------------------------------------------------------
# Small generic helpers
# ---------------------------------------------------------------------------

function Resolve-AbsolutePath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$BaseDirectory
    )
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }
    return [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($BaseDirectory, $Path))
}

function Trim-DirectorySeparators {
    param([Parameter(Mandatory = $true)][string]$Path)
    return $Path.TrimEnd([char[]]@('\', '/'))
}

function Test-PathIsUnder {
    param(
        [Parameter(Mandatory = $true)][string]$Candidate,
        [Parameter(Mandatory = $true)][string]$Root
    )
    $rootTrimmed = Trim-DirectorySeparators -Path $Root
    if ($rootTrimmed.Length -eq 0) { return $false }
    $rootWithSeparator = $rootTrimmed + [System.IO.Path]::DirectorySeparatorChar
    if ($Candidate.Length -le $rootWithSeparator.Length) { return $false }
    return $Candidate.StartsWith($rootWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-RepoRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$FullPath,
        [Parameter(Mandatory = $true)][string]$RepoRootFull
    )
    $rootWithSeparator = (Trim-DirectorySeparators -Path $RepoRootFull) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $FullPath.StartsWith($rootWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw ("Path is not under the repository root: " + $FullPath)
    }
    return $FullPath.Substring($rootWithSeparator.Length).Replace('\', '/')
}

function Join-RepoPath {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRootFull,
        [Parameter(Mandatory = $true)][string]$RelativePath
    )
    return [System.IO.Path]::Combine($RepoRootFull, $RelativePath.Replace('/', [System.IO.Path]::DirectorySeparatorChar))
}

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Path)
    $hash = Get-FileHash -LiteralPath $Path -Algorithm SHA256
    return $hash.Hash.ToLowerInvariant()
}

function Format-ByteSize {
    param([Parameter(Mandatory = $true)][long]$Bytes)
    $kib = [math]::Round(([double]$Bytes / 1024.0), 2)
    return (('' + $Bytes) + ' bytes / ' + (('' + $kib)) + ' KiB')
}

# ---------------------------------------------------------------------------
# Exclusion rules
# ---------------------------------------------------------------------------

function Test-ExcludedDirectoryName {
    param([Parameter(Mandatory = $true)][string]$Name)
    $lower = $Name.ToLowerInvariant()
    if ($lower -eq '.git') { return $true }
    if ($lower -eq '_scratch') { return $true }
    if ($lower -eq '__pycache__') { return $true }
    if ($lower -eq '.venv') { return $true }
    if ($lower -eq 'venv') { return $true }
    if ($lower -eq 'node_modules') { return $true }
    return $false
}

function Test-ExcludedRepoRelativePath {
    param([Parameter(Mandatory = $true)][string]$RelativePath)
    $rel = $RelativePath.Replace('\', '/')
    if ($rel.Length -eq 0) { return $true }

    $segments = $rel.Split('/')
    for ($index = 0; $index -lt ($segments.Length - 1); $index++) {
        if (Test-ExcludedDirectoryName -Name $segments[$index]) { return $true }
    }

    $leafLower = ($segments[$segments.Length - 1]).ToLowerInvariant()
    if ($leafLower.EndsWith('.pyc')) { return $true }
    if ($leafLower.EndsWith('.zip')) { return $true }

    $relLower = $rel.ToLowerInvariant()
    if ($relLower.StartsWith('results/')) {
        if ($relLower.StartsWith('results/demo/') -or $relLower -eq 'results/demo') {
            return $false
        }
        return $true
    }
    return $false
}

# ---------------------------------------------------------------------------
# Secret detection
# ---------------------------------------------------------------------------

function Test-SecretFileName {
    param([Parameter(Mandatory = $true)][string]$FileName)
    $lower = $FileName.ToLowerInvariant()
    if ($lower -eq '.env') { return 'dotenv file' }
    if ($lower.StartsWith('.env.')) { return 'environment file' }
    if ($lower.EndsWith('.pem')) { return 'PEM certificate or key file' }
    if ($lower.EndsWith('.key')) { return 'key file' }
    if ($lower.StartsWith('id_rsa')) { return 'SSH private key file' }
    if ($lower -eq '.npmrc') { return 'npm auth config file' }
    if ($lower -eq '.pypirc') { return 'PyPI auth config file' }
    if ($lower -eq 'credentials.json') { return 'credentials file' }
    if ($lower.StartsWith('secrets.')) { return 'secrets file' }
    if ($lower.EndsWith('.pfx')) { return 'PKCS#12 bundle' }
    if ($lower.EndsWith('.p12')) { return 'PKCS#12 bundle' }
    return ''
}

function New-SecretContentRule {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$Pattern
    )
    $regex = New-Object System.Text.RegularExpressions.Regex($Pattern)
    return [pscustomobject]@{
        Label = $Label
        Regex = $regex
    }
}

function Test-BytesLookBinary {
    param([Parameter(Mandatory = $true)][byte[]]$Bytes)
    $limit = 8192
    if ($Bytes.Length -lt $limit) { $limit = $Bytes.Length }
    for ($index = 0; $index -lt $limit; $index++) {
        if ($Bytes[$index] -eq 0) { return $true }
    }
    return $false
}

function Test-SyntheticSecretValue {
    # The test suite legitimately contains obviously fake credentials used to
    # prove that the runner redacts them (for example sk-DUMMYKEY... or
    # "do-not-print" values). Values carrying a clear synthetic marker are
    # ignored so the secret guard blocks real leaks without blocking the
    # offline test fixtures. A real credential does not contain these markers.
    param([Parameter(Mandatory = $true)][string]$Value)
    if ([string]::IsNullOrEmpty($Value)) { return $false }
    $markers = '(?i)(dummy|fake|example|placeholder|not[-_]?a[-_]?real|notreal|do[-_]?not[-_]?print|redact|synthetic|bogus|mock|sample|xxxx|change[-_]?me|replace[-_]?me|your[-_]?token|test[-_]?token|testtoken|invalid[-_]?key|invalid[-_]?token)'
    return [regex]::IsMatch($Value, $markers)
}

function Find-SecretFindings {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRootFull,
        [Parameter(Mandatory = $true)][string[]]$RelativeFiles,
        [Parameter(Mandatory = $true)][int]$MaxScanBytes
    )

    $privateKeyPattern = '-----BEGIN ' + '[A-Z ]*PRIVATE KEY-----'

    $contentRules = @(
        New-SecretContentRule -Label 'GitHub classic token' -Pattern 'ghp_[A-Za-z0-9]{36}'
        New-SecretContentRule -Label 'GitHub fine-grained token' -Pattern 'github_pat_[A-Za-z0-9_]{20,}'
        New-SecretContentRule -Label 'AWS access key id' -Pattern 'AKIA[0-9A-Z]{16}'
        New-SecretContentRule -Label 'private key block' -Pattern $privateKeyPattern
        New-SecretContentRule -Label 'api key / secret / token assignment' -Pattern '(?i)(api[_-]?key|secret|token)\s*[:=]\s*[''"][A-Za-z0-9_\-]{24,}[''"]'
        New-SecretContentRule -Label 'OpenAI-style secret key' -Pattern 'sk-[A-Za-z0-9]{20,}'
        New-SecretContentRule -Label 'Slack token' -Pattern 'xox[baprs]-[A-Za-z0-9-]{10,}'
    )

    $findings = New-Object 'System.Collections.Generic.List[string]'
    $scannedCount = 0
    $binarySkippedCount = 0
    $oversizedSkippedCount = 0
    $unreadableCount = 0
    $syntheticSkippedCount = 0
    $syntheticWarningsPrinted = 0

    foreach ($relativePath in $RelativeFiles) {
        $leafName = [System.IO.Path]::GetFileName($relativePath)
        $fileNameRule = Test-SecretFileName -FileName $leafName
        if ($fileNameRule.Length -gt 0) {
            [void]$findings.Add('[filename] ' + $relativePath + ' (' + $fileNameRule + ')')
        }

        $fullPath = Join-RepoPath -RepoRootFull $RepoRootFull -RelativePath $relativePath
        $fileInfo = New-Object System.IO.FileInfo($fullPath)
        if (-not $fileInfo.Exists) {
            $unreadableCount = $unreadableCount + 1
            continue
        }
        if ($fileInfo.Length -gt $MaxScanBytes) {
            $oversizedSkippedCount = $oversizedSkippedCount + 1
            continue
        }

        try {
            $bytes = [System.IO.File]::ReadAllBytes($fullPath)
        }
        catch {
            Write-ArchiveWarn ('could not read file for secret scan (skipped): ' + $relativePath)
            $unreadableCount = $unreadableCount + 1
            continue
        }

        if (Test-BytesLookBinary -Bytes $bytes) {
            $binarySkippedCount = $binarySkippedCount + 1
            continue
        }

        $scannedCount = $scannedCount + 1
        $text = [System.Text.Encoding]::UTF8.GetString($bytes)
        $lineNumber = 0
        foreach ($line in ($text -split "\r?\n")) {
            $lineNumber = $lineNumber + 1
            foreach ($rule in $contentRules) {
                $ruleMatches = $rule.Regex.Matches($line)
                if ($ruleMatches.Count -eq 0) { continue }
                $syntheticOnly = $true
                foreach ($ruleMatch in $ruleMatches) {
                    if (-not (Test-SyntheticSecretValue -Value $ruleMatch.Value)) {
                        $syntheticOnly = $false
                        break
                    }
                }
                if ($syntheticOnly) {
                    $syntheticSkippedCount = $syntheticSkippedCount + 1
                    if ($syntheticWarningsPrinted -lt 20) {
                        Write-ArchiveWarn ('ignoring synthetic test credential at ' + $relativePath + ':' + $lineNumber + ' (' + $rule.Label + '); no value is shown')
                        $syntheticWarningsPrinted = $syntheticWarningsPrinted + 1
                    }
                    break
                }
                [void]$findings.Add('[content] ' + $relativePath + ':' + $lineNumber + ' (' + $rule.Label + ')')
                break
            }
        }
    }

    return [pscustomobject]@{
        Findings = $findings
        ScannedCount = $scannedCount
        BinarySkippedCount = $binarySkippedCount
        OversizedSkippedCount = $oversizedSkippedCount
        UnreadableCount = $unreadableCount
        SyntheticSkippedCount = $syntheticSkippedCount
        Rules = $contentRules.Count
    }
}

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

function Format-NativeArgument {
    param([Parameter(Mandatory = $true)][string]$Value)
    if ($Value -match '[\s"]') {
        return ('"' + ($Value -replace '"', '\"') + '"')
    }
    return $Value
}

function Invoke-GitCapture {
    param(
        [Parameter(Mandatory = $true)][string]$GitExe,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$StagingRoot,
        [string]$WorkingDirectory = ''
    )

    $token = [System.Guid]::NewGuid().ToString('N')
    $stdoutPath = [System.IO.Path]::Combine($StagingRoot, 'git-' + $token + '.stdout')
    $stderrPath = [System.IO.Path]::Combine($StagingRoot, 'git-' + $token + '.stderr')

    try {
        $quotedArguments = New-Object 'System.Collections.Generic.List[string]'
        foreach ($argument in $Arguments) {
            [void]$quotedArguments.Add((Format-NativeArgument -Value $argument))
        }

        $startParameters = @{
            FilePath = $GitExe
            ArgumentList = $quotedArguments.ToArray()
            RedirectStandardOutput = $stdoutPath
            RedirectStandardError = $stderrPath
            NoNewWindow = $true
            Wait = $true
            PassThru = $true
        }
        if ($WorkingDirectory.Length -gt 0) {
            $startParameters['WorkingDirectory'] = $WorkingDirectory
        }

        $process = Start-Process @startParameters
        $exitCode = $process.ExitCode

        $stdout = ''
        if (Test-Path -LiteralPath $stdoutPath -PathType Leaf) {
            $stdout = [System.IO.File]::ReadAllText($stdoutPath, [System.Text.Encoding]::UTF8)
        }
        $stderr = ''
        if (Test-Path -LiteralPath $stderrPath -PathType Leaf) {
            $stderr = [System.IO.File]::ReadAllText($stderrPath, [System.Text.Encoding]::UTF8)
        }

        return [pscustomobject]@{
            ExitCode = $exitCode
            StdOut = $stdout
            StdErr = $stderr
        }
    }
    finally {
        Remove-Item -LiteralPath $stdoutPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

function Resolve-GitExecutable {
    param(
        [string]$ExplicitPath,
        [Parameter(Mandatory = $true)][string]$RepoRootFull,
        [Parameter(Mandatory = $true)][string]$ScriptRepoRoot,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        $resolved = Resolve-AbsolutePath -Path $ExplicitPath -BaseDirectory $WorkingDirectory
        if (Test-Path -LiteralPath $resolved -PathType Leaf) {
            return (Get-Item -LiteralPath $resolved).FullName
        }
        $command = Get-Command $ExplicitPath -ErrorAction SilentlyContinue
        if ($null -ne $command) { return $command.Source }
        return ''
    }

    $candidates = New-Object 'System.Collections.Generic.List[string]'
    [void]$candidates.Add([System.IO.Path]::Combine($RepoRootFull, '_scratch\Git\bin\git.exe'))
    [void]$candidates.Add([System.IO.Path]::Combine($ScriptRepoRoot, '_scratch\Git\bin\git.exe'))

    if (-not [string]::IsNullOrWhiteSpace($env:FAILBENCH_GIT)) {
        [void]$candidates.Add($env:FAILBENCH_GIT)
    }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Get-Item -LiteralPath $candidate).FullName
        }
    }

    $command = Get-Command git -ErrorAction SilentlyContinue
    if ($null -ne $command) { return $command.Source }
    return ''
}

# ---------------------------------------------------------------------------
# ZIP archive creation
# ---------------------------------------------------------------------------

function New-SourceArchive {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRootFull,
        [Parameter(Mandatory = $true)][string[]]$RelativeFiles,
        [Parameter(Mandatory = $true)][string]$StagingZipPath
    )

    if (Test-Path -LiteralPath $StagingZipPath) {
        Remove-Item -LiteralPath $StagingZipPath -Force
    }

    $writtenCount = 0
    $skippedCount = 0
    $fileStream = [System.IO.File]::Open($StagingZipPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite)
    try {
        $zipArchive = New-Object System.IO.Compression.ZipArchive($fileStream, [System.IO.Compression.ZipArchiveMode]::Create, $true)
        try {
            foreach ($relativePath in $RelativeFiles) {
                $fullPath = Join-RepoPath -RepoRootFull $RepoRootFull -RelativePath $relativePath
                $entryName = $relativePath.Replace('\', '/')

                try {
                    $sourceStream = [System.IO.File]::OpenRead($fullPath)
                }
                catch [System.IO.FileNotFoundException] {
                    Write-ArchiveWarn ('file disappeared before archiving (skipped): ' + $relativePath)
                    $skippedCount = $skippedCount + 1
                    continue
                }
                catch [System.IO.DirectoryNotFoundException] {
                    Write-ArchiveWarn ('file disappeared before archiving (skipped): ' + $relativePath)
                    $skippedCount = $skippedCount + 1
                    continue
                }
                catch [System.IO.IOException] {
                    Write-ArchiveWarn ('file is locked or unreadable (skipped): ' + $relativePath)
                    $skippedCount = $skippedCount + 1
                    continue
                }

                try {
                    $entry = $zipArchive.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
                    try {
                        $lastWrite = (New-Object System.IO.FileInfo($fullPath)).LastWriteTime
                        if ($lastWrite.Year -ge 1980 -and $lastWrite.Year -le 2107) {
                            $entry.LastWriteTime = [System.DateTimeOffset]$lastWrite
                        }
                    }
                    catch {
                        # Timestamp metadata is cosmetic; ignore race conditions here.
                    }

                    $entryStream = $entry.Open()
                    try {
                        $sourceStream.CopyTo($entryStream)
                    }
                    finally {
                        $entryStream.Dispose()
                    }
                    $writtenCount = $writtenCount + 1
                }
                finally {
                    $sourceStream.Dispose()
                }
            }
        }
        finally {
            $zipArchive.Dispose()
        }
    }
    finally {
        $fileStream.Dispose()
    }

    return [pscustomobject]@{
        EntryCount = $writtenCount
        SkippedCount = $skippedCount
    }
}

# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

function Invoke-FailBenchArchive {
    [CmdletBinding()]
    param(
        [string]$RepoRoot,
        [string]$Version,
        [string]$OutDir,
        [string]$GitPath,
        [switch]$SkipBundle
    )

    $workingDirectory = (Get-Location).Path
    $scriptRepoRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($script:ScriptDirectory, '..', '..'))
    $maxScanBytes = 2 * 1024 * 1024

    Write-ArchiveInfo 'FailBench release archive builder'
    Write-ArchiveInfo ('PowerShell: ' + $PSVersionTable.PSVersion.ToString() + ' / ' + $PSVersionTable.PSEdition)

    # --- 1. Resolve repository root ----------------------------------------
    if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
        $repoRootFull = Trim-DirectorySeparators -Path $scriptRepoRoot
        Write-ArchiveInfo ('repository root (derived from script location): ' + $repoRootFull)
    }
    else {
        $repoRootFull = Trim-DirectorySeparators -Path (Resolve-AbsolutePath -Path $RepoRoot -BaseDirectory $workingDirectory)
    }

    if (-not (Test-Path -LiteralPath $repoRootFull -PathType Container)) {
        Write-ArchiveError ('repository root does not exist or is not a directory: ' + $repoRootFull)
        return 1
    }
    $repoRootFull = (Get-Item -LiteralPath $repoRootFull).FullName
    Write-ArchiveInfo ('repository root: ' + $repoRootFull)

    # --- 2. Validate version ------------------------------------------------
    $versionTrimmed = ''
    if (-not [string]::IsNullOrWhiteSpace($Version)) {
        $versionTrimmed = $Version.Trim()
    }
    if ($versionTrimmed -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') {
        Write-ArchiveError ('invalid -Version ''{0}'': expected semantic version like 0.1.0 (pattern ^\d+\.\d+\.\d+$)' -f $Version)
        return 1
    }
    $safeVersion = $versionTrimmed -replace '[^0-9A-Za-z._-]', '_'
    Write-ArchiveInfo ('version: ' + $safeVersion)

    # --- 3. Resolve output directory ---------------------------------------
    if ([string]::IsNullOrWhiteSpace($OutDir)) {
        $outDirFull = [System.IO.Path]::Combine($repoRootFull, '_scratch\dist')
    }
    else {
        $outDirFull = Resolve-AbsolutePath -Path $OutDir -BaseDirectory $workingDirectory
    }
    $outDirFull = Trim-DirectorySeparators -Path $outDirFull
    if (-not (Test-Path -LiteralPath $outDirFull -PathType Container)) {
        [void](New-Item -ItemType Directory -Path $outDirFull -Force)
        Write-ArchiveInfo ('created output directory: ' + $outDirFull)
    }
    else {
        Write-ArchiveInfo ('output directory: ' + $outDirFull)
    }

    $zipName = 'failbench-v' + $safeVersion + '.zip'
    $bundleName = 'failbench-v' + $safeVersion + '.bundle'
    $checksumsName = 'SHA256SUMS.txt'
    $zipPath = [System.IO.Path]::Combine($outDirFull, $zipName)
    $bundlePath = [System.IO.Path]::Combine($outDirFull, $bundleName)
    $checksumsPath = [System.IO.Path]::Combine($outDirFull, $checksumsName)

    if ($outDirFull -eq $repoRootFull) {
        Write-ArchiveWarn 'output directory equals the repository root; artifacts are added after the file list is captured.'
    }

    # Output directory subtree is never archived (avoids stale artifacts).
    $isOutDirInsideRepo = $false
    $outDirRelativePrefix = ''
    if ($outDirFull -ne $repoRootFull -and (Test-PathIsUnder -Candidate $outDirFull -Root $repoRootFull)) {
        $isOutDirInsideRepo = $true
        $outDirRelative = Get-RepoRelativePath -FullPath $outDirFull -RepoRootFull $repoRootFull
        $outDirRelativePrefix = (Trim-DirectorySeparators -Path $outDirRelative).Replace('\', '/') + '/'
        Write-ArchiveInfo ('output directory is inside the repository and is excluded from the archive: ' + $outDirRelativePrefix)
    }

    # --- 4. Resolve git -----------------------------------------------------
    $repoIsGit = Test-Path -LiteralPath ([System.IO.Path]::Combine($repoRootFull, '.git'))
    Write-ArchiveInfo ('git repository at repo root: ' + $(if ($repoIsGit) { 'yes' } else { 'no' }))

    $gitExecutable = Resolve-GitExecutable -ExplicitPath $GitPath -RepoRootFull $repoRootFull -ScriptRepoRoot $scriptRepoRoot -WorkingDirectory $workingDirectory
    if ($gitExecutable.Length -eq 0) {
        if (-not [string]::IsNullOrWhiteSpace($GitPath)) {
            Write-ArchiveError ('git executable not found: ' + $GitPath)
            return 1
        }
        Write-ArchiveWarn 'git executable not found; falling back to a directory walk and skipping the git bundle.'
    }
    else {
        Write-ArchiveInfo ('git executable: ' + $gitExecutable)
    }

    # --- 5. Enumerate candidate files ---------------------------------------
    $relativeFiles = New-Object 'System.Collections.Generic.List[string]'
    $useGitFileList = ($repoIsGit -and $gitExecutable.Length -gt 0)

    if ($useGitFileList) {
        Write-ArchiveInfo 'file selection: git ls-files (tracked files only)'
        $gitResult = Invoke-GitCapture -GitExe $gitExecutable -Arguments @('-C', $repoRootFull, 'ls-files', '-z') -StagingRoot $script:TempRoot
        if ($gitResult.ExitCode -ne 0) {
            throw ('git ls-files failed with exit code ' + $gitResult.ExitCode + ': ' + $gitResult.StdErr.Trim())
        }

        $entries = @()
        if ($gitResult.StdOut.Length -gt 0) {
            $entries = $gitResult.StdOut.Split([char]0)
        }

        foreach ($entry in $entries) {
            if ($entry.Length -eq 0) { continue }
            $relativePath = $entry.Replace('\', '/')
            if ($relativePath.StartsWith('/') -or $relativePath.StartsWith('../')) {
                Write-ArchiveWarn ('skipping unsafe git path: ' + $relativePath)
                continue
            }
            if (Test-ExcludedRepoRelativePath -RelativePath $relativePath) { continue }
            if ($isOutDirInsideRepo -and $relativePath.StartsWith($outDirRelativePrefix, [System.StringComparison]::OrdinalIgnoreCase)) { continue }

            $fullPath = Join-RepoPath -RepoRootFull $repoRootFull -RelativePath $relativePath
            if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
                Write-ArchiveWarn ('tracked file missing from the working tree (skipped): ' + $relativePath)
                continue
            }
            [void]$relativeFiles.Add($relativePath)
        }
    }
    else {
        Write-ArchiveInfo 'file selection: directory walk (no git file list available)'
        $queue = New-Object 'System.Collections.Generic.Queue[string]'
        $queue.Enqueue($repoRootFull)

        while ($queue.Count -gt 0) {
            $currentDirectory = $queue.Dequeue()

            $childFiles = @()
            try {
                $childFiles = [System.IO.Directory]::GetFiles($currentDirectory)
            }
            catch {
                Write-ArchiveWarn ('cannot list files in directory (skipped): ' + $currentDirectory)
            }

            foreach ($fileFullPath in $childFiles) {
                $relativePath = Get-RepoRelativePath -FullPath $fileFullPath -RepoRootFull $repoRootFull
                if (Test-ExcludedRepoRelativePath -RelativePath $relativePath) { continue }
                if ($isOutDirInsideRepo -and $relativePath.StartsWith($outDirRelativePrefix, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
                [void]$relativeFiles.Add($relativePath)
            }

            $childDirectories = @()
            try {
                $childDirectories = [System.IO.Directory]::GetDirectories($currentDirectory)
            }
            catch {
                Write-ArchiveWarn ('cannot list subdirectories (skipped): ' + $currentDirectory)
            }

            foreach ($directoryFullPath in $childDirectories) {
                if (Test-ExcludedDirectoryName -Name ([System.IO.Path]::GetFileName($directoryFullPath))) { continue }
                if ($isOutDirInsideRepo) {
                    $directoryRelative = (Get-RepoRelativePath -FullPath $directoryFullPath -RepoRootFull $repoRootFull).Replace('\', '/')
                    if (($directoryRelative + '/').StartsWith($outDirRelativePrefix, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
                }
                $queue.Enqueue($directoryFullPath)
            }
        }
    }

    # Deduplicate and sort with an ordinal comparer for deterministic entry order.
    $uniqueFiles = New-Object 'System.Collections.Generic.List[string]'
    $seenFiles = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($relativePath in $relativeFiles) {
        if ($seenFiles.Add($relativePath)) {
            [void]$uniqueFiles.Add($relativePath)
        }
    }
    $sortedFiles = $uniqueFiles.ToArray()
    [Array]::Sort($sortedFiles, [System.StringComparer]::Ordinal)

    Write-ArchiveInfo ('candidate files: ' + $sortedFiles.Length)
    if ($sortedFiles.Length -eq 0) {
        Write-ArchiveWarn 'no files were selected for archiving; the source ZIP will be empty.'
    }

    # --- 6. Secret guard ----------------------------------------------------
    $scanResult = Find-SecretFindings -RepoRootFull $repoRootFull -RelativeFiles $sortedFiles -MaxScanBytes $maxScanBytes
    if ($scanResult.Findings.Count -gt 0) {
        Write-ArchiveError 'secret-like content detected - refusing to archive'
        $reported = 0
        foreach ($finding in $scanResult.Findings) {
            if ($reported -ge 50) { break }
            Write-Host ('  ' + $finding)
            $reported = $reported + 1
        }
        if ($scanResult.Findings.Count -gt $reported) {
            Write-Host ('  ... and ' + ($scanResult.Findings.Count - $reported) + ' more')
        }
        Write-ArchiveInfo 'no new artifacts were written. Remove the listed files (or add them to .gitignore), then re-run.'
        return 2
    }
    Write-ArchiveOk ('secret scan: clean (' + $scanResult.ScannedCount + ' text files scanned, ' + $scanResult.BinarySkippedCount + ' binary skipped, ' + $scanResult.OversizedSkippedCount + ' oversized skipped, ' + $scanResult.Rules + ' content rules, ' + $scanResult.SyntheticSkippedCount + ' synthetic test values ignored)')

    # --- 7. Remove stale artifacts -----------------------------------------
    foreach ($stalePath in @($zipPath, $bundlePath, $checksumsPath)) {
        if (Test-Path -LiteralPath $stalePath -PathType Leaf) {
            Remove-Item -LiteralPath $stalePath -Force
        }
    }

    # --- 8. Build the source ZIP -------------------------------------------
    $stagingZipPath = [System.IO.Path]::Combine($script:TempRoot, $zipName)
    $archiveResult = New-SourceArchive -RepoRootFull $repoRootFull -RelativeFiles $sortedFiles -StagingZipPath $stagingZipPath
    Move-Item -LiteralPath $stagingZipPath -Destination $zipPath -Force
    if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) {
        throw ('source ZIP was not created: ' + $zipPath)
    }

    # --- 9. Build the git bundle -------------------------------------------
    $bundleCreated = $false
    $bundleRefCount = 0
    $bundleWarnMessage = '[WARN] git bundle skipped: no initialized git repository at repo root (or no commits). Run make_archive.ps1 again after the root has committed.'

    if ($SkipBundle) {
        Write-ArchiveInfo 'git bundle skipped (-SkipBundle was specified).'
    }
    elseif (-not $repoIsGit) {
        Write-ArchiveWarn ('git bundle skipped: no initialized git repository at repo root (or no commits). Run make_archive.ps1 again after the root has committed.')
    }
    elseif ($gitExecutable.Length -eq 0) {
        Write-ArchiveWarn 'git bundle skipped: git executable not found.'
    }
    else {
        $bundleResult = Invoke-GitCapture -GitExe $gitExecutable -Arguments @('-C', $repoRootFull, 'bundle', 'create', $bundlePath, '--all') -StagingRoot $script:TempRoot
        if ($bundleResult.ExitCode -ne 0) {
            Write-ArchiveWarn ('git bundle skipped: no initialized git repository at repo root (or no commits). Run make_archive.ps1 again after the root has committed.')
            $bundleError = $bundleResult.StdErr.Trim()
            if ($bundleError.Length -gt 0) {
                Write-ArchiveInfo ('git said: ' + $bundleError)
            }
            if (Test-Path -LiteralPath $bundlePath -PathType Leaf) {
                Remove-Item -LiteralPath $bundlePath -Force -ErrorAction SilentlyContinue
            }
        }
        elseif (-not (Test-Path -LiteralPath $bundlePath -PathType Leaf)) {
            Write-ArchiveWarn ('git bundle skipped: no initialized git repository at repo root (or no commits). Run make_archive.ps1 again after the root has committed.')
        }
        else {
            $bundleCreated = $true
            $headsResult = Invoke-GitCapture -GitExe $gitExecutable -Arguments @('-C', $repoRootFull, 'bundle', 'list-heads', $bundlePath) -StagingRoot $script:TempRoot
            if ($headsResult.ExitCode -eq 0) {
                $headLines = @($headsResult.StdOut -split "\r?\n" | Where-Object { $_.Trim().Length -gt 0 })
                $bundleRefCount = $headLines.Length
            }
        }
    }

    # --- 10. Write SHA256SUMS.txt ------------------------------------------
    $artifactPaths = @($zipPath)
    if ($bundleCreated) {
        $artifactPaths += $bundlePath
    }

    $sumLines = New-Object 'System.Collections.Generic.List[string]'
    foreach ($artifactPath in $artifactPaths) {
        $artifactHash = Get-Sha256Hex -Path $artifactPath
        [void]$sumLines.Add($artifactHash + '  ' + [System.IO.Path]::GetFileName($artifactPath))
    }
    $sumText = ($sumLines -join "`n") + "`n"
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($checksumsPath, $sumText, $utf8NoBom)

    # --- 11. Summary --------------------------------------------------------
    $zipBytes = (New-Object System.IO.FileInfo($zipPath)).Length
    $zipHash = Get-Sha256Hex -Path $zipPath

    Write-ArchiveOk ('file selection: ' + $(if ($useGitFileList) { 'git ls-files' } else { 'directory walk' }) + ' (' + $sortedFiles.Length + ' files)')
    Write-ArchiveOk ('secret scan: clean (' + $scanResult.ScannedCount + ' text files scanned)')
    Write-ArchiveOk ('source zip: ' + $zipPath + ' (' + $archiveResult.EntryCount + ' entries, ' + (Format-ByteSize -Bytes $zipBytes) + ')')
    Write-ArchiveOk ('source zip sha256: ' + $zipHash)
    if ($archiveResult.SkippedCount -gt 0) {
        Write-ArchiveWarn ('source zip: ' + $archiveResult.SkippedCount + ' file(s) were skipped during archiving.')
    }
    if ($bundleCreated) {
        $bundleBytes = (New-Object System.IO.FileInfo($bundlePath)).Length
        $bundleHash = Get-Sha256Hex -Path $bundlePath
        Write-ArchiveOk ('git bundle: ' + $bundlePath + ' (' + (Format-ByteSize -Bytes $bundleBytes) + ', ' + $bundleRefCount + ' refs)')
        Write-ArchiveOk ('git bundle sha256: ' + $bundleHash)
    }
    Write-ArchiveOk ('checksums file: ' + $checksumsPath + ' (' + $sumLines.Count + ' entries, LF line endings, no BOM)')
    Write-ArchiveOk ('output directory: ' + $outDirFull)
    Write-ArchiveOk 'done.'

    return 0
}

# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

$script:ScriptDirectory = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($script:ScriptDirectory)) {
    $script:ScriptDirectory = (Get-Location).Path
}
$script:TempRoot = ''

$mainExitCode = 1
try {
    # System.IO.Compression ships with Windows PowerShell 5.1 and PowerShell 7.
    try {
        Add-Type -AssemblyName System.IO.Compression -ErrorAction Stop
    }
    catch {
        # PowerShell 7 usually resolves the type without loading the assembly.
    }
    try {
        $null = [System.IO.Compression.ZipArchive]
    }
    catch {
        Add-Type -AssemblyName System.IO.Compression -ErrorAction Stop
        $null = [System.IO.Compression.ZipArchive]
    }

    $script:TempRoot = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), ('failbench-archive-' + [System.Guid]::NewGuid().ToString('N')))
    [void](New-Item -ItemType Directory -Path $script:TempRoot -Force)

    $mainExitCode = Invoke-FailBenchArchive -RepoRoot $RepoRoot -Version $Version -OutDir $OutDir -GitPath $GitPath -SkipBundle:$SkipBundle
}
catch {
    Write-ArchiveError ($_.Exception.Message)
    $stackLine = ''
    if (-not [string]::IsNullOrEmpty($_.ScriptStackTrace)) {
        $stackLine = ([string]$_.ScriptStackTrace).Split("`n")[0].Trim()
    }
    if ($stackLine.Length -gt 0) {
        Write-Host ('[ERROR] at ' + $stackLine)
    }
    $mainExitCode = 1
}
finally {
    if (-not [string]::IsNullOrWhiteSpace($script:TempRoot) -and (Test-Path -LiteralPath $script:TempRoot)) {
        Remove-Item -LiteralPath $script:TempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

exit $mainExitCode
