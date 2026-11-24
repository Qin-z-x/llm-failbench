<#
.SYNOPSIS
    Publish the FailBench repository to GitHub safely and idempotently.

.DESCRIPTION
    One-command publish helper for this repository. It validates the inputs, reuses
    or initializes the local git repository, sets the local commit identity, stages
    and commits the working tree, creates the GitHub repository through the REST API
    when it does not exist, and pushes the main branch.

    The default mode is a DRY RUN. It prints every git command and every HTTP request
    it would perform, but it does not modify files, does not run git commands that
    write, and makes no network calls. Pass -Execute to publish for real.

    The GitHub token is read only from the GITHUB_TOKEN environment variable. It is
    never a parameter, never prompted for, never stored on disk, and never printed.
    Push authentication uses per-process environment variables only, so the token is
    not written into .git/config, the remote URL, or any other file.

.PARAMETER UserName
    GitHub user or organization that owns (or will own) the repository. Required.

.PARAMETER RepoName
    Repository name. Default: llm-failbench.

.PARAMETER UserEmail
    Commit email for the local git identity. Optional. When omitted, the GitHub
    noreply address "<UserName>@users.noreply.github.com" is used.

.PARAMETER Description
    Repository description sent to the GitHub API. Maximum 350 characters.

.PARAMETER Private
    Create the GitHub repository as private. Default is public.

.PARAMETER Execute
    Actually perform the publish. Without this switch the script only prints a plan.

.PARAMETER GitPath
    Optional explicit path to git.exe, or to the bin directory that contains git.exe.

.PARAMETER RepoRoot
    Optional advanced/testing override for the repository root. The default is the
    root of the checkout that contains this script (two directory levels above
    scripts/publish).

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\publish\publish.ps1 -UserName your-github-handle -UserEmail you@users.noreply.github.com

    Dry run: prints the full publish plan and changes nothing.

.EXAMPLE
    $env:GITHUB_TOKEN = '<classic PAT with repo and workflow scopes>'
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\publish\publish.ps1 -UserName your-github-handle -UserEmail you@users.noreply.github.com -Execute

    Publishes the repository, reusing an existing local or remote repository when present.

.NOTES
    FailBench v0.1.0 publish helper. Compatible with Windows PowerShell 5.1 and
    PowerShell 7. Portable-git aware. The token is never printed or persisted.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$UserName,
    [string]$RepoName = 'llm-failbench',
    [string]$UserEmail = '',
    [string]$Description = 'The evidence-backed, judge-free failure probe kit for LLMs.',
    [switch]$Private,
    [switch]$Execute,
    [string]$GitPath = '',
    [string]$RepoRoot = ''
)

Set-StrictMode -Version Latest

# ---------------------------------------------------------------------------
# Script state and constants
# ---------------------------------------------------------------------------
$script:ScriptVersion = '0.1.0'
$script:UserAgent = 'failbench-publish-script/0.1.0'
$script:CommitMessage = 'release: failbench v0.1.0'
$script:BranchName = 'main'
$script:ApiVersion = '2022-11-28'
$script:Token = ''
$script:GitExe = ''
$script:GitVersion = ''
$script:GitVersionMajor = 0
$script:GitVersionMinor = 0
$script:GitSupportsInitB = $false
$script:ResolvedRepoRoot = ''
$script:SavedEnvironment = @{}
$script:ExitCode = 0
$script:HandledFatal = $false
$global:LASTEXITCODE = 0

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
function Write-Info {
    param([string]$Message)
    Write-Host ('[INFO] ' + $Message)
}

function Write-Plan {
    param([string]$Message)
    Write-Host ('[PLAN] ' + $Message) -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host ('[OK] ' + $Message) -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host ('[WARN] ' + $Message) -ForegroundColor Yellow
}

function Write-ErrorLine {
    param([string]$Message)
    Write-Host ('[ERROR] ' + $Message) -ForegroundColor Red
}

function Write-Section {
    param([string]$Title)
    Write-Host ''
    Write-Host ('=' * 74) -ForegroundColor DarkCyan
    Write-Host $Title -ForegroundColor Cyan
    Write-Host ('=' * 74) -ForegroundColor DarkCyan
}

# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------
function Redact {
    # Masks the active token and common GitHub token shapes in any text that is
    # about to be printed or logged. Never returns the token itself.
    param([string]$Text)
    if ([string]::IsNullOrEmpty($Text)) {
        return ''
    }
    $result = [string]$Text
    if (-not [string]::IsNullOrEmpty($script:Token)) {
        $result = $result.Replace($script:Token, '***')
    }
    $result = [regex]::Replace($result, 'gh[pousr]_[A-Za-z0-9]{10,}', '***')
    $result = [regex]::Replace($result, 'github_pat_[A-Za-z0-9_]{10,}', '***')
    $result = [regex]::Replace($result, '(?i)(authorization\s*:\s*(?:bearer|basic)\s+)\S+', '${1}***')
    return $result
}

function Stop-Publish {
    # Prints a fatal error block (redacted) and aborts the publish flow. The
    # top-level catch handler turns the abort into exit code 1.
    param([string[]]$MessageLines)
    foreach ($line in $MessageLines) {
        Write-ErrorLine (Redact ([string]$line))
    }
    $script:HandledFatal = $true
    throw ('PUBLISH_ABORTED')
}

function Get-DisplayValue {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return '(not set)'
    }
    return $Value
}

function Get-TrimmedText {
    param([string]$Text, [int]$MaxLength = 300)
    if ([string]::IsNullOrEmpty($Text)) {
        return ''
    }
    $cleaned = [regex]::Replace($Text, '\s+', ' ').Trim()
    if ($cleaned.Length -le $MaxLength) {
        return $cleaned
    }
    return $cleaned.Substring(0, $MaxLength) + '...'
}

function Resolve-FullPath {
    param([string]$PathValue)
    $unresolved = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PathValue)
    return [System.IO.Path]::GetFullPath($unresolved)
}

function Test-PathSamePath {
    param([string]$PathA, [string]$PathB)
    if ([string]::IsNullOrWhiteSpace($PathA) -or [string]::IsNullOrWhiteSpace($PathB)) {
        return $false
    }
    $normalizedA = $PathA.Replace('/', '\').TrimEnd('\')
    $normalizedB = $PathB.Replace('/', '\').TrimEnd('\')
    return [string]::Equals($normalizedA, $normalizedB, [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-UnderScratchPath {
    param([string]$FullPath)
    if ([string]::IsNullOrWhiteSpace($FullPath)) {
        return $false
    }
    $normalized = $FullPath.Replace('/', '\')
    return [regex]::IsMatch($normalized, '(?i)(^|\\)_scratch(\\|$)')
}

function Resolve-RepoRoot {
    # Resolves and sanity-checks the target repository root. In DRY RUN this only
    # reads the filesystem.
    param([string]$ProvidedRoot)

    $provided = -not [string]::IsNullOrWhiteSpace($ProvidedRoot)
    $candidate = ''
    if ($provided) {
        try {
            $candidate = Resolve-FullPath $ProvidedRoot
        } catch {
            Stop-Publish -MessageLines @(
                ('Could not resolve the -RepoRoot path: ' + $ProvidedRoot),
                $_.Exception.Message
            )
        }
    } else {
        if ([string]::IsNullOrWhiteSpace($PSScriptRoot)) {
            Stop-Publish -MessageLines @(
                'Cannot derive the repository root because $PSScriptRoot is empty.',
                'Pass -RepoRoot explicitly.'
            )
        }
        $publishDirectory = [System.IO.Path]::GetDirectoryName($PSScriptRoot)
        $derivedRoot = ''
        if (-not [string]::IsNullOrWhiteSpace($publishDirectory)) {
            $derivedRoot = [System.IO.Path]::GetDirectoryName($publishDirectory)
        }
        if ([string]::IsNullOrWhiteSpace($derivedRoot)) {
            Stop-Publish -MessageLines @('Could not derive the repository root from the script location. Pass -RepoRoot explicitly.')
        }
        $candidate = Resolve-FullPath $derivedRoot
    }

    if (-not (Test-Path -LiteralPath $candidate)) {
        Stop-Publish -MessageLines @(
            ('Repository root does not exist: ' + $candidate),
            'Create the checkout first, or pass a valid -RepoRoot.'
        )
    }
    if (-not (Test-Path -LiteralPath $candidate -PathType Container)) {
        Stop-Publish -MessageLines @(('Repository root is not a directory: ' + $candidate))
    }

    $trimmedCandidate = $candidate.TrimEnd('\')
    if ($trimmedCandidate -match '(?i)\\_scratch$') {
        Stop-Publish -MessageLines @(
            ('Refusing to publish the _scratch directory itself: ' + $candidate),
            'Point -RepoRoot at the real repository root instead.'
        )
    }

    $entryCount = @(Get-ChildItem -LiteralPath $candidate -Force -ErrorAction Stop).Count
    if ($entryCount -eq 0) {
        Stop-Publish -MessageLines @(
            ('Repository root looks empty: ' + $candidate),
            'Refusing to publish an empty directory. Check out the repository first.'
        )
    }

    if (Test-UnderScratchPath $candidate) {
        if ($provided) {
            Write-Warn ('repository root is under _scratch (' + $candidate + '); continuing because -RepoRoot was passed explicitly (test mode)')
        } else {
            Stop-Publish -MessageLines @(
                ('Refusing to publish a derived repository root under _scratch: ' + $candidate),
                'Pass the real repository root, or -RepoRoot explicitly for a testing copy.'
            )
        }
    }

    return $candidate
}

function Format-GitCommand {
    param([string[]]$GitArguments)
    $displayParts = New-Object System.Collections.Generic.List[string]
    foreach ($argument in $GitArguments) {
        if ($null -eq $argument) {
            continue
        }
        $text = [string]$argument
        if ($text -match '\s') {
            $displayParts.Add("'" + $text + "'")
        } else {
            $displayParts.Add($text)
        }
    }
    return ('  $ git ' + [string]::Join(' ', $displayParts.ToArray()))
}

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------
function Invoke-Git {
    # Runs git and returns { ExitCode, Output } with stdout and stderr combined.
    # ErrorActionPreference is relaxed locally because native stderr redirected
    # with 2>&1 becomes error records under Windows PowerShell 5.1.
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string[]]$GitArguments,
        [string]$GitExecutable = ''
    )
    $executable = $GitExecutable
    if ([string]::IsNullOrWhiteSpace($executable)) {
        $executable = $script:GitExe
    }
    if ([string]::IsNullOrWhiteSpace($executable)) {
        return [pscustomobject]@{ ExitCode = 127; Output = 'git executable has not been resolved yet' }
    }

    $capturedLines = @()
    $exitCode = 0
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $global:LASTEXITCODE = 0
        $capturedLines = @(& $executable @GitArguments 2>&1 | ForEach-Object { $_.ToString() })
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }

    return [pscustomobject]@{
        ExitCode = [int]$exitCode
        Output   = [string]($capturedLines -join [Environment]::NewLine)
    }
}

function Get-GitVersionInfo {
    param([string]$GitExecutable)
    $result = Invoke-Git -GitArguments @('--version') -GitExecutable $GitExecutable
    if ($result.ExitCode -ne 0) {
        return $null
    }
    $match = [regex]::Match([string]$result.Output, 'git version (\d+)\.(\d+)\.(\d+)')
    if (-not $match.Success) {
        return $null
    }
    $major = [int]$match.Groups[1].Value
    $minor = [int]$match.Groups[2].Value
    $patch = [int]$match.Groups[3].Value
    if ($major -lt 2) {
        Write-Warn ('Rejected git ' + $major + '.' + $minor + '.' + $patch + ' at ' + $GitExecutable + ': version 2.0 or newer is required.')
        return $null
    }
    $supportsInitB = (($major -gt 2) -or (($major -eq 2) -and ($minor -ge 28)))
    return [pscustomobject]@{
        VersionText  = ('{0}.{1}.{2}' -f $major, $minor, $patch)
        Major        = $major
        Minor        = $minor
        Patch        = $patch
        SupportsInitB = $supportsInitB
    }
}

function Expand-GitCandidate {
    param([string]$CandidatePath)
    if ([string]::IsNullOrWhiteSpace($CandidatePath)) {
        return ''
    }
    if (Test-Path -LiteralPath $CandidatePath -PathType Container) {
        return (Join-Path $CandidatePath 'git.exe')
    }
    return $CandidatePath
}

function Resolve-GitExecutable {
    param(
        [string]$ExplicitGitPath,
        [string]$PublishRoot,
        [string]$ScriptCheckoutRoot
    )

    $candidates = New-Object System.Collections.Generic.List[object]

    if (-not [string]::IsNullOrWhiteSpace($ExplicitGitPath)) {
        $explicitFull = Expand-GitCandidate (Resolve-FullPath $ExplicitGitPath)
        if (-not (Test-Path -LiteralPath $explicitFull -PathType Leaf)) {
            Stop-Publish -MessageLines @(
                ('-GitPath was provided but no git executable was found at: ' + $explicitFull),
                'Pass either the full path to git.exe or the bin directory that contains it.'
            )
        }
        [void]$candidates.Add([pscustomobject]@{ Path = $explicitFull; Source = '-GitPath'; Strict = $true })
    }

    if (-not [string]::IsNullOrWhiteSpace($env:FAILBENCH_GIT)) {
        $environmentFull = Expand-GitCandidate (Resolve-FullPath $env:FAILBENCH_GIT)
        if (Test-Path -LiteralPath $environmentFull -PathType Leaf) {
            [void]$candidates.Add([pscustomobject]@{ Path = $environmentFull; Source = 'FAILBENCH_GIT'; Strict = $false })
        } else {
            Write-Warn ('FAILBENCH_GIT points to a missing git executable (' + $environmentFull + '); ignoring it.')
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($PublishRoot)) {
        [void]$candidates.Add([pscustomobject]@{
            Path   = (Join-Path $PublishRoot '_scratch\Git\bin\git.exe')
            Source = 'portable git under the repo root'
            Strict = $false
        })
    }

    if (-not [string]::IsNullOrWhiteSpace($ScriptCheckoutRoot) -and -not (Test-PathSamePath $PublishRoot $ScriptCheckoutRoot)) {
        [void]$candidates.Add([pscustomobject]@{
            Path   = (Join-Path $ScriptCheckoutRoot '_scratch\Git\bin\git.exe')
            Source = 'portable git in the script checkout'
            Strict = $false
        })
    }

    $pathCommand = Get-Command -Name 'git' -ErrorAction SilentlyContinue
    if ($null -ne $pathCommand) {
        $pathExecutable = ''
        if ($null -ne $pathCommand.Source) {
            $pathExecutable = [string]$pathCommand.Source
        } elseif ($null -ne $pathCommand.Path) {
            $pathExecutable = [string]$pathCommand.Path
        }
        if (-not [string]::IsNullOrWhiteSpace($pathExecutable)) {
            [void]$candidates.Add([pscustomobject]@{ Path = $pathExecutable; Source = 'git on PATH'; Strict = $false })
        }
    }

    $rejected = New-Object System.Collections.Generic.List[string]
    foreach ($candidate in $candidates) {
        if (-not (Test-Path -LiteralPath $candidate.Path -PathType Leaf)) {
            continue
        }
        $versionInfo = Get-GitVersionInfo -GitExecutable $candidate.Path
        if ($null -eq $versionInfo) {
            [void]$rejected.Add(($candidate.Path + ' (' + $candidate.Source + ')'))
            continue
        }
        $script:GitExe = $candidate.Path
        $script:GitVersion = $versionInfo.VersionText
        $script:GitVersionMajor = $versionInfo.Major
        $script:GitVersionMinor = $versionInfo.Minor
        $script:GitSupportsInitB = $versionInfo.SupportsInitB
        Write-Ok ('git found via ' + $candidate.Source + ': ' + $candidate.Path + ' (git version ' + $versionInfo.VersionText + ')')
        if (-not $versionInfo.SupportsInitB) {
            Write-Warn ('git ' + $versionInfo.VersionText + " is older than 2.28: 'git init -b' is unavailable, so the script falls back to 'git init' plus a branch rename.")
        }
        return
    }

    $failureLines = New-Object System.Collections.Generic.List[string]
    $failureLines.Add('git 2.0 or newer was not found or is not usable.')
    if ($rejected.Count -gt 0) {
        $failureLines.Add('Rejected candidates:')
        foreach ($rejectedCandidate in $rejected) {
            $failureLines.Add('  - ' + $rejectedCandidate)
        }
    }
    $failureLines.Add('Fix one of the following and rerun:')
    $failureLines.Add('  - Pass -GitPath <path to git.exe or its bin directory>')
    $failureLines.Add('  - Set the FAILBENCH_GIT environment variable to git.exe')
    $failureLines.Add('  - Install Git for Windows (or portable git under _scratch\Git\bin) so git.exe is found')
    Stop-Publish -MessageLines ($failureLines.ToArray())
}

function Test-GitHeadExists {
    param([string]$RootPath)
    $result = Invoke-Git -GitArguments @('-C', $RootPath, 'rev-parse', '--verify', '--quiet', 'HEAD')
    if ($result.ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($result.Output)) {
        return $true
    }
    return $false
}

function Get-GitHeadHash {
    param([string]$RootPath, [switch]$Short)
    $arguments = @('-C', $RootPath, 'rev-parse')
    if ($Short.IsPresent) {
        $arguments = @('-C', $RootPath, 'rev-parse', '--short')
    }
    $arguments = @($arguments + 'HEAD')
    $result = Invoke-Git -GitArguments $arguments
    if ($result.ExitCode -eq 0) {
        return $result.Output.Trim()
    }
    return ''
}

# ---------------------------------------------------------------------------
# HTTP helpers (EXECUTE mode only)
# ---------------------------------------------------------------------------
function Enable-Tls12ForWindowsPowerShell {
    if ($PSVersionTable.PSVersion.Major -ge 6) {
        return
    }
    try {
        $currentProtocol = [int][System.Net.ServicePointManager]::SecurityProtocol
        $tls12Value = [int][System.Net.SecurityProtocolType]::Tls12
        if (($currentProtocol -band $tls12Value) -ne $tls12Value) {
            $combined = $currentProtocol -bor $tls12Value
            [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]$combined
        }
    } catch {
        Write-Warn ('Could not enable TLS 1.2 for Windows PowerShell: ' + $_.Exception.Message)
    }
}

function Get-HttpStatusCode {
    param([object]$ErrorRecord)
    try {
        if ($null -eq $ErrorRecord) {
            return 0
        }
        $response = $ErrorRecord.Exception.Response
        if ($null -eq $response) {
            return 0
        }
        $rawStatus = $null
        if ($null -ne $response.PSObject.Properties['StatusCode']) {
            $rawStatus = $response.StatusCode
        } elseif ($null -ne $response.PSObject.Properties['Status']) {
            $rawStatus = $response.Status
        }
        if ($null -eq $rawStatus) {
            return 0
        }
        try {
            return [int]$rawStatus
        } catch {
            return 0
        }
    } catch {
        return 0
    }
}

function Get-HttpErrorBody {
    param([object]$ErrorRecord)
    if ($null -eq $ErrorRecord) {
        return ''
    }
    $bodyText = ''
    try {
        if ($null -ne $ErrorRecord.ErrorDetails -and $null -ne $ErrorRecord.ErrorDetails.Message) {
            $bodyText = [string]$ErrorRecord.ErrorDetails.Message
        }
    } catch {
        $bodyText = ''
    }
    if ([string]::IsNullOrEmpty($bodyText)) {
        try {
            $response = $ErrorRecord.Exception.Response
            if ($null -ne $response) {
                if ($null -ne $response.PSObject.Methods['ReadAsStringAsync']) {
                    $bodyText = [string]$response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
                } elseif ($null -ne $response.PSObject.Methods['GetResponseStream']) {
                    $stream = $response.GetResponseStream()
                    if ($null -ne $stream) {
                        $reader = New-Object System.IO.StreamReader($stream)
                        try {
                            $bodyText = [string]$reader.ReadToEnd()
                        } finally {
                            $reader.Dispose()
                        }
                    }
                }
            }
        } catch {
            $bodyText = ''
        }
    }
    return $bodyText
}

function Invoke-GitHubRequest {
    # Minimal, version-tolerant wrapper around Invoke-WebRequest. Returns the HTTP
    # status code and the response body for both success and failure responses.
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][hashtable]$Headers,
        [string]$Body = ''
    )

    Enable-Tls12ForWindowsPowerShell

    $requestParameters = @{
        Uri         = $Uri
        Method      = $Method
        Headers     = $Headers
        UserAgent   = $script:UserAgent
        TimeoutSec  = 30
        ErrorAction = 'Stop'
    }
    if ($PSVersionTable.PSVersion.Major -lt 6) {
        $requestParameters['UseBasicParsing'] = $true
    }
    if (-not [string]::IsNullOrEmpty($Body)) {
        $requestParameters['Body'] = $Body
        $requestParameters['ContentType'] = 'application/json; charset=utf-8'
    }

    $statusCode = 0
    $responseBody = ''
    try {
        $response = Invoke-WebRequest @requestParameters
        $statusCode = [int]$response.StatusCode
        $responseBody = [string]$response.Content
    } catch {
        $statusCode = Get-HttpStatusCode -ErrorRecord $_
        $responseBody = Get-HttpErrorBody -ErrorRecord $_
    }

    return [pscustomobject]@{
        StatusCode = [int]$statusCode
        Body       = [string]$responseBody
    }
}

# ---------------------------------------------------------------------------
# Push credential environment helpers
# ---------------------------------------------------------------------------
function Set-GitAuthEnvironment {
    # Stores the previous values of the push-related environment variables and
    # sets the process-only credential configuration. The token never touches
    # disk and is never passed in argv.
    param([string]$BasicCredential)
    $variableNames = @('GIT_CONFIG_COUNT', 'GIT_CONFIG_KEY_0', 'GIT_CONFIG_VALUE_0', 'GIT_TERMINAL_PROMPT', 'GCM_INTERACTIVE')
    foreach ($variableName in $variableNames) {
        $script:SavedEnvironment[$variableName] = [Environment]::GetEnvironmentVariable($variableName, 'Process')
    }
    $env:GIT_CONFIG_COUNT = '1'
    $env:GIT_CONFIG_KEY_0 = 'http.https://github.com/.extraheader'
    $env:GIT_CONFIG_VALUE_0 = 'AUTHORIZATION: basic ' + $BasicCredential
    $env:GIT_TERMINAL_PROMPT = '0'
    $env:GCM_INTERACTIVE = 'never'
}

function Restore-ProcessEnvironment {
    # Restores the process environment variables changed for the push. Idempotent.
    if ($null -eq $script:SavedEnvironment) {
        return
    }
    foreach ($variableName in @($script:SavedEnvironment.Keys)) {
        $savedValue = $script:SavedEnvironment[$variableName]
        if ($null -eq $savedValue) {
            Remove-Item -LiteralPath ('Env:' + $variableName) -ErrorAction SilentlyContinue
        } else {
            Set-Item -LiteralPath ('Env:' + $variableName) -Value $savedValue -ErrorAction SilentlyContinue
        }
        $script:SavedEnvironment.Remove($variableName)
    }
}

function Get-PushFailureHints {
    param([string]$OutputText)
    $hints = New-Object System.Collections.Generic.List[string]
    if ($OutputText -match '(?i)non-fast-forward|fetch first|rejected') {
        $hints.Add('The remote has commits this checkout does not have. Pull/rebase first, or publish to a fresh repository.')
    }
    if ($OutputText -match '(?i)authentication failed|could not read username|terminal prompts disabled|HTTP 401|HTTP 403') {
        $hints.Add('Authentication failed: confirm GITHUB_TOKEN is a valid classic PAT with the repo scope and is set in this process.')
    }
    if ($OutputText -match '(?i)workflow') {
        $hints.Add('The token needs the workflow scope to push files under .github/workflows.')
    }
    if ($OutputText -match '(?i)does not match any|src refspec') {
        $hints.Add('No local commit exists on the target branch yet; commit before pushing.')
    }
    if ($OutputText -match '(?i)unable to access|failed to connect|network|proxy|timed out') {
        $hints.Add('Network error: check connectivity or proxy settings and retry.')
    }
    if ($hints.Count -eq 0) {
        $hints.Add('Check the origin URL, token scopes, and branch state, then retry.')
    }
    return ($hints.ToArray())
}

# ===========================================================================
# Main flow
# ===========================================================================
try {
    Write-Host ''
    Write-Host 'FailBench publish helper (v0.1.0)' -ForegroundColor White

    # ------------------------------------------------------------------
    # Input validation (no writes, no git, no network)
    # ------------------------------------------------------------------
    $inputErrors = New-Object System.Collections.Generic.List[string]
    if (-not ($UserName -match '^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$')) {
        $inputErrors.Add(("UserName must be 1-39 characters matching a GitHub login (letters, digits, hyphen; starting with a letter or digit). Got: '" + $UserName + "'"))
    }
    if ([string]::IsNullOrEmpty($RepoName) -or -not ($RepoName -match '^[A-Za-z0-9._-]{1,100}$') -or $RepoName -eq '.' -or $RepoName -eq '..') {
        $inputErrors.Add(("RepoName must be 1-100 characters of letters, digits, dot, underscore or hyphen, and must not be '.' or '..'. Got: '" + $RepoName + "'"))
    }
    if ([string]::IsNullOrWhiteSpace($Description)) {
        $Description = ''
    }
    if ($Description.Length -gt 350) {
        $inputErrors.Add(('Description must be 350 characters or fewer. Got ' + $Description.Length + ' characters.'))
    }
    $emailDefaulted = $false
    if ([string]::IsNullOrWhiteSpace($UserEmail)) {
        $UserEmail = $UserName + '@users.noreply.github.com'
        $emailDefaulted = $true
    } elseif (-not $UserEmail.Contains('@') -or $UserEmail -match '\s') {
        $inputErrors.Add(("UserEmail must contain '@' and no whitespace. Got: '" + $UserEmail + "'"))
    }
    if ($inputErrors.Count -gt 0) {
        $validationLines = New-Object System.Collections.Generic.List[string]
        $validationLines.Add('Invalid arguments; nothing was changed:')
        foreach ($inputError in $inputErrors) {
            $validationLines.Add('  - ' + $inputError)
        }
        Stop-Publish -MessageLines ($validationLines.ToArray())
    }

    $isExecute = $Execute.IsPresent
    $isPrivate = $Private.IsPresent
    $repoUrl = 'https://github.com/' + $UserName + '/' + $RepoName

    Write-Host ''
    if ($isExecute) {
        Write-Host 'MODE: EXECUTE' -ForegroundColor Red
    } else {
        Write-Host 'MODE: DRY RUN (no changes, no network writes)' -ForegroundColor Yellow
    }
    Write-Host ''

    # ------------------------------------------------------------------
    # [1/7] Environment
    # ------------------------------------------------------------------
    Write-Section '[1/7] Environment'

    if ($emailDefaulted) {
        Write-Warn ('UserEmail not provided; using GitHub noreply form ' + $UserEmail + ' (pass -UserEmail to use your real commit email)')
    }

    $script:Token = ''
    if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) {
        $script:Token = [string]$env:GITHUB_TOKEN.Trim()
    }
    $tokenStatus = 'not set - required for -Execute'
    if ($script:Token.Length -gt 0) {
        $tokenStatus = 'present (value never shown)'
    }

    if ($isExecute -and $script:Token.Length -eq 0) {
        Stop-Publish -MessageLines @(
            'GITHUB_TOKEN is not set. -Execute requires a GitHub token; no git or network commands were run.',
            'Fix:',
            '  1. Create a classic personal access token at https://github.com/settings/tokens/new',
            "     with scopes 'repo' and 'workflow' (workflow is required to push .github/workflows files).",
            '  2. In the same PowerShell window set: $env:GITHUB_TOKEN = <the-token-value>',
            '  3. Rerun this script with -Execute.'
        )
    }

    $script:ResolvedRepoRoot = Resolve-RepoRoot -ProvidedRoot $RepoRoot
    if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
        Write-Info ('repository root (derived from script location): ' + $script:ResolvedRepoRoot)
    } else {
        Write-Info ('repository root (from -RepoRoot): ' + $script:ResolvedRepoRoot)
    }

    $scriptCheckoutRoot = $script:ResolvedRepoRoot
    if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot)) {
        $publishDirectory = [System.IO.Path]::GetDirectoryName($PSScriptRoot)
        if (-not [string]::IsNullOrWhiteSpace($publishDirectory)) {
            $derivedCheckout = [System.IO.Path]::GetDirectoryName($publishDirectory)
            if (-not [string]::IsNullOrWhiteSpace($derivedCheckout)) {
                $scriptCheckoutRoot = Resolve-FullPath $derivedCheckout
            }
        }
    }

    Resolve-GitExecutable -ExplicitGitPath $GitPath -PublishRoot $script:ResolvedRepoRoot -ScriptCheckoutRoot $scriptCheckoutRoot

    $visibility = 'public'
    if ($isPrivate) {
        $visibility = 'private'
    }
    Write-Host ''
    Write-Host ('  git            : ' + $script:GitExe)
    Write-Host ('  git version    : ' + $script:GitVersion)
    Write-Host ('  repo root      : ' + $script:ResolvedRepoRoot)
    Write-Host ('  target repo    : ' + $repoUrl)
    Write-Host ('  visibility     : ' + $visibility)
    Write-Host ('  commit identity: ' + $UserName + ' <' + $UserEmail + '>')
    Write-Host ('  GITHUB_TOKEN   : ' + $tokenStatus)

    # ------------------------------------------------------------------
    # [2/7] Repo state
    # ------------------------------------------------------------------
    Write-Section '[2/7] Repo state'

    $repoExists = $false
    $headExists = $false
    $currentHeadFull = ''
    $currentHeadShort = ''
    $currentBranch = ''
    $gitDirectory = Join-Path $script:ResolvedRepoRoot '.git'

    if (Test-Path -LiteralPath $gitDirectory) {
        $repoExists = $true
        Write-Ok 'existing git repository detected, reusing'
        $headExists = Test-GitHeadExists -RootPath $script:ResolvedRepoRoot
        if ($headExists) {
            $currentHeadFull = Get-GitHeadHash -RootPath $script:ResolvedRepoRoot
            $currentHeadShort = Get-GitHeadHash -RootPath $script:ResolvedRepoRoot -Short
            $branchResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'rev-parse', '--abbrev-ref', 'HEAD')
            if ($branchResult.ExitCode -eq 0) {
                $currentBranch = $branchResult.Output.Trim()
            }
            Write-Info ('current HEAD: ' + $currentHeadShort + ' on branch ' + (Get-DisplayValue $currentBranch))
        } else {
            $symbolicResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'symbolic-ref', '--short', 'HEAD')
            if ($symbolicResult.ExitCode -eq 0) {
                $currentBranch = $symbolicResult.Output.Trim()
            }
            Write-Info ('repository has no commits yet; current branch: ' + (Get-DisplayValue $currentBranch))
        }
    }

    if (-not $repoExists) {
        if ($isExecute) {
            if ($script:GitSupportsInitB) {
                $initArguments = @('-C', $script:ResolvedRepoRoot, 'init', '-b', $script:BranchName)
            } else {
                $initArguments = @('-C', $script:ResolvedRepoRoot, 'init')
            }
            $initResult = Invoke-Git -GitArguments $initArguments
            if ($initResult.ExitCode -ne 0) {
                Stop-Publish -MessageLines @(
                    ('git init failed with exit code ' + $initResult.ExitCode + '.'),
                    ('git said: ' + (Redact $initResult.Output))
                )
            }
            $repoExists = $true
            $branchAfterInit = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'symbolic-ref', '--short', 'HEAD')
            if ($branchAfterInit.ExitCode -eq 0) {
                $currentBranch = $branchAfterInit.Output.Trim()
            }
            Write-Ok 'initialized a new git repository'
        } else {
            if ($script:GitSupportsInitB) {
                Write-Plan (Format-GitCommand -GitArguments @('-C', $script:ResolvedRepoRoot, 'init', '-b', $script:BranchName))
            } else {
                Write-Plan (Format-GitCommand -GitArguments @('-C', $script:ResolvedRepoRoot, 'init'))
            }
            Write-Info 'dry run: no .git directory was created'
        }
    }

    # Local commit identity: only written when missing or different.
    $currentName = ''
    $currentEmail = ''
    if ($repoExists) {
        $nameResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'config', '--local', '--get', 'user.name')
        if ($nameResult.ExitCode -eq 0) {
            $currentName = $nameResult.Output.Trim()
        }
        $emailResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'config', '--local', '--get', 'user.email')
        if ($emailResult.ExitCode -eq 0) {
            $currentEmail = $emailResult.Output.Trim()
        }
    }

    if ($isExecute) {
        if ($repoExists) {
            if ($currentName -ne $UserName) {
                $setNameResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'config', '--local', 'user.name', $UserName)
                if ($setNameResult.ExitCode -ne 0) {
                    Stop-Publish -MessageLines @(
                        'Failed to set the local git user.name.',
                        ('git said: ' + (Redact $setNameResult.Output))
                    )
                }
                Write-Ok ('set local git user.name to ' + $UserName + ' (was: ' + (Get-DisplayValue $currentName) + ')')
            } else {
                Write-Ok ('local git user.name already ' + $UserName + ', no change')
            }
            if ($currentEmail -ne $UserEmail) {
                $setEmailResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'config', '--local', 'user.email', $UserEmail)
                if ($setEmailResult.ExitCode -ne 0) {
                    Stop-Publish -MessageLines @(
                        'Failed to set the local git user.email.',
                        ('git said: ' + (Redact $setEmailResult.Output))
                    )
                }
                Write-Ok ('set local git user.email to ' + $UserEmail + ' (was: ' + (Get-DisplayValue $currentEmail) + ')')
            } else {
                Write-Ok ('local git user.email already ' + $UserEmail + ', no change')
            }
        }
    } else {
        Write-Info ('current local user.name : ' + (Get-DisplayValue $currentName))
        Write-Info ('current local user.email: ' + (Get-DisplayValue $currentEmail))
        Write-Plan (Format-GitCommand -GitArguments @('-C', $script:ResolvedRepoRoot, 'config', '--local', 'user.name', $UserName))
        Write-Plan (Format-GitCommand -GitArguments @('-C', $script:ResolvedRepoRoot, 'config', '--local', 'user.email', $UserEmail))
        Write-Info 'identity config is only written when missing or different (no change in dry run)'
    }

    # ------------------------------------------------------------------
    # [3/7] Commit
    # ------------------------------------------------------------------
    Write-Section '[3/7] Commit'

    $dryRunChangeCount = 0
    if ($isExecute) {
        $addResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'add', '-A')
        if ($addResult.ExitCode -ne 0) {
            Stop-Publish -MessageLines @(
                ('git add -A failed with exit code ' + $addResult.ExitCode + '.'),
                ('git said: ' + (Redact $addResult.Output))
            )
        }
        Write-Ok 'staged the working tree with git add -A (.gitignore respected)'

        $headBeforeCommit = Test-GitHeadExists -RootPath $script:ResolvedRepoRoot
        $stagedDiffResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'diff', '--cached', '--quiet')
        if ($stagedDiffResult.ExitCode -eq 0) {
            Write-Ok 'nothing new to commit (working tree clean)'
            if (-not $headBeforeCommit) {
                Stop-Publish -MessageLines @(
                    'Nothing is staged and the repository has no commits yet.',
                    'Refusing to publish an empty repository; check .gitignore and the working tree.'
                )
            }
        } elseif ($stagedDiffResult.ExitCode -eq 1) {
            $commitResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'commit', '-m', $script:CommitMessage)
            if ($commitResult.ExitCode -ne 0) {
                Stop-Publish -MessageLines @(
                    ('git commit failed with exit code ' + $commitResult.ExitCode + '.'),
                    ('git said: ' + (Redact $commitResult.Output))
                )
            }
            $newHeadShort = Get-GitHeadHash -RootPath $script:ResolvedRepoRoot -Short
            Write-Ok ('committed: ' + $script:CommitMessage + ' (' + $newHeadShort + ')')
        } else {
            Stop-Publish -MessageLines @(
                ('git diff --cached --quiet failed with exit code ' + $stagedDiffResult.ExitCode + '.'),
                ('git said: ' + (Redact $stagedDiffResult.Output))
            )
        }
    } else {
        Write-Plan (Format-GitCommand -GitArguments @('-C', $script:ResolvedRepoRoot, 'add', '-A'))
        if ($repoExists) {
            $statusResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'status', '--porcelain')
            if ($statusResult.ExitCode -eq 0) {
                $statusLines = @()
                if (-not [string]::IsNullOrWhiteSpace($statusResult.Output)) {
                    $statusLines = @($statusResult.Output -split '\r?\n' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
                }
                $untrackedCount = 0
                $modifiedCount = 0
                foreach ($statusLine in $statusLines) {
                    if ($statusLine.Length -ge 2) {
                        if ($statusLine.Substring(0, 2) -eq '??') {
                            $untrackedCount = $untrackedCount + 1
                        } else {
                            $modifiedCount = $modifiedCount + 1
                        }
                    }
                }
                $dryRunChangeCount = $statusLines.Count
                Write-Info ('status: ' + $untrackedCount + ' untracked, ' + $modifiedCount + ' modified/staged (read-only)')
                $fileListResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'ls-files', '--cached', '--others', '--exclude-standard')
                if ($fileListResult.ExitCode -eq 0) {
                    $fileCount = 0
                    if (-not [string]::IsNullOrWhiteSpace($fileListResult.Output)) {
                        $fileCount = @($fileListResult.Output -split '\r?\n' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }).Count
                    }
                    Write-Info ('working tree files: ' + $fileCount + ' tracked or untracked, .gitignore respected')
                }
            } else {
                Write-Warn 'could not read git status during the dry run'
            }
        } else {
            Write-Info 'no git repository yet, so no status summary is available; git add -A would stage the working tree'
        }

        Write-Info ('planned commit message: ' + $script:CommitMessage)
        Write-Plan (Format-GitCommand -GitArguments @('-C', $script:ResolvedRepoRoot, 'commit', '-m', $script:CommitMessage))
        if ($repoExists) {
            if ($dryRunChangeCount -eq 0 -and $headExists) {
                Write-Info 'working tree already clean; the real run would create no new commit'
            } elseif ($dryRunChangeCount -eq 0 -and -not $headExists) {
                Write-Info 'no changes found yet; the real run would create the first commit from the working tree'
            } else {
                Write-Info ('changes present: the real run would create a commit with ' + $dryRunChangeCount + ' status entries')
            }
        } else {
            Write-Info 'the first commit would be created by the real run'
        }
    }

    # Ensure the branch is main.
    $branchNow = ''
    $headForBranch = $false
    if ($repoExists) {
        $headForBranch = Test-GitHeadExists -RootPath $script:ResolvedRepoRoot
        if ($headForBranch) {
            $branchResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'rev-parse', '--abbrev-ref', 'HEAD')
            if ($branchResult.ExitCode -eq 0) {
                $branchNow = $branchResult.Output.Trim()
            }
        }
        if ([string]::IsNullOrWhiteSpace($branchNow) -or $branchNow -eq 'HEAD') {
            $symbolicResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'symbolic-ref', '--short', 'HEAD')
            if ($symbolicResult.ExitCode -eq 0) {
                $branchNow = $symbolicResult.Output.Trim()
            }
        }
    }

    if (-not $repoExists) {
        if ($script:GitSupportsInitB) {
            Write-Ok ("branch will be '" + $script:BranchName + "' (created by git init -b)")
        } else {
            Write-Plan (Format-GitCommand -GitArguments @('-C', $script:ResolvedRepoRoot, 'branch', '-M', $script:BranchName))
        }
    } elseif ($branchNow -eq $script:BranchName) {
        Write-Ok ("branch is '" + $script:BranchName + "'")
    } else {
        if ($isExecute) {
            $renameResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'branch', '-M', $script:BranchName)
            if ($renameResult.ExitCode -ne 0) {
                if (-not $headForBranch) {
                    $symbolicReset = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'symbolic-ref', 'HEAD', ('refs/heads/' + $script:BranchName))
                    if ($symbolicReset.ExitCode -ne 0) {
                        Stop-Publish -MessageLines @(
                            ('Could not switch the repository to branch ' + $script:BranchName + '.'),
                            ('git said: ' + (Redact $renameResult.Output))
                        )
                    }
                    Write-Warn ('renamed the unborn branch to ' + $script:BranchName + ' using symbolic-ref (git branch -M was unavailable)')
                } else {
                    Stop-Publish -MessageLines @(
                        ('git branch -M ' + $script:BranchName + ' failed.'),
                        ('git said: ' + (Redact $renameResult.Output))
                    )
                }
            } else {
                Write-Ok ('renamed branch ' + (Get-DisplayValue $branchNow) + ' to ' + $script:BranchName)
            }
        } else {
            Write-Plan (Format-GitCommand -GitArguments @('-C', $script:ResolvedRepoRoot, 'branch', '-M', $script:BranchName))
        }
    }

    # ------------------------------------------------------------------
    # [4/7] GitHub repo
    # ------------------------------------------------------------------
    Write-Section '[4/7] GitHub repo'

    $apiRepoUrl = 'https://api.github.com/repos/' + $UserName + '/' + $RepoName
    $apiCreateUrl = 'https://api.github.com/user/repos'
    $repoPayload = [ordered]@{
        name         = $RepoName
        description  = $Description
        private      = [bool]$isPrivate
        has_issues   = $true
        has_wiki     = $false
        has_projects = $false
        auto_init    = $false
    }
    $repoJson = $repoPayload | ConvertTo-Json -Compress -Depth 5
    $authHeaders = @{
        'Authorization'       = 'Bearer ' + $script:Token
        'Accept'              = 'application/vnd.github+json'
        'X-GitHub-Api-Version' = $script:ApiVersion
    }

    if (-not $isExecute) {
        Write-Plan ('HTTP GET  ' + $apiRepoUrl + '   (read-only existence pre-check)')
        Write-Plan ('HTTP POST ' + $apiCreateUrl + '   (only when the repository does not exist)')
        Write-Plan '  request headers:'
        Write-Plan '    Authorization: Bearer *** (read from GITHUB_TOKEN; never printed)'
        Write-Plan ('    User-Agent: ' + $script:UserAgent)
        Write-Plan '    Accept: application/vnd.github+json'
        Write-Plan ('    X-GitHub-Api-Version: ' + $script:ApiVersion)
        Write-Plan ('  request body: ' + $repoJson)
        Write-Info 'dry run: no network requests were made'
    } else {
        Write-Info ('checking whether ' + $repoUrl + ' already exists (read-only GET)')
        $preCheckResult = Invoke-GitHubRequest -Method 'GET' -Uri $apiRepoUrl -Headers $authHeaders
        $remoteRepoExists = $false
        if ($preCheckResult.StatusCode -eq 200) {
            Write-Ok 'repository already exists, continuing (idempotent)'
            $remoteRepoExists = $true
        } elseif ($preCheckResult.StatusCode -eq 404) {
            Write-Info 'repository does not exist yet; creating it with the GitHub REST API'
        } else {
            Write-Warn ('could not confirm repository existence (HTTP ' + $preCheckResult.StatusCode + '); attempting creation anyway. Detail: ' + (Get-TrimmedText -Text (Redact $preCheckResult.Body) -MaxLength 200))
        }

        if (-not $remoteRepoExists) {
            Write-Info ('creating GitHub repository ' + $repoUrl)
            $createResult = Invoke-GitHubRequest -Method 'POST' -Uri $apiCreateUrl -Headers $authHeaders -Body $repoJson
            switch ($createResult.StatusCode) {
                201 {
                    Write-Ok ('created GitHub repository ' + $repoUrl)
                }
                422 {
                    Write-Warn ('GitHub returned HTTP 422 (repository already exists); continuing idempotently. Detail: ' + (Get-TrimmedText -Text (Redact $createResult.Body) -MaxLength 200))
                }
                401 {
                    Stop-Publish -MessageLines @(
                        'GitHub token rejected (HTTP 401). The token is invalid, expired, or malformed, so no push will be attempted.',
                        'Fix: create a new classic PAT at https://github.com/settings/tokens/new with the repo scope',
                        "     (add the workflow scope when the repository contains .github/workflows).",
                        '     Then set $env:GITHUB_TOKEN to the new token and rerun with -Execute.'
                    )
                }
                403 {
                    Stop-Publish -MessageLines @(
                        'GitHub API returned HTTP 403 (forbidden). Common causes: the token is missing the repo scope,',
                        'organization SSO is not authorized for this token, or the API rate limit is exhausted.',
                        'Fix: check the PAT scopes, authorize SSO for the organization, or wait for the rate-limit reset',
                        '     (see https://api.github.com/rate_limit), then rerun with -Execute.'
                    )
                }
                default {
                    Stop-Publish -MessageLines @(
                        ('Creating the GitHub repository failed (HTTP ' + $createResult.StatusCode + ').'),
                        ('response: ' + (Get-TrimmedText -Text (Redact $createResult.Body) -MaxLength 300)),
                        'Check the username, token scopes, and network or proxy settings.'
                    )
                }
            }
        }
    }

    # ------------------------------------------------------------------
    # [5/7] Push
    # ------------------------------------------------------------------
    Write-Section '[5/7] Push'

    $originUrl = $repoUrl + '.git'
    $basicCredential = ''
    if ($script:Token.Length -gt 0) {
        $basicCredential = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes('x-access-token:' + $script:Token))
    }

    if (-not $isExecute) {
        Write-Plan ('origin URL: ' + $originUrl)
        Write-Plan (Format-GitCommand -GitArguments @('-C', $script:ResolvedRepoRoot, 'remote', 'set-url', 'origin', $originUrl) + '   (or: remote add origin <url> when origin is missing)')
        Write-Plan (Format-GitCommand -GitArguments @('-C', $script:ResolvedRepoRoot, 'push', '-u', 'origin', $script:BranchName))
        Write-Plan '  per-process environment for the push (removed afterwards):'
        Write-Plan '    GIT_CONFIG_COUNT=1'
        Write-Plan '    GIT_CONFIG_KEY_0=http.https://github.com/.extraheader'
        Write-Plan '    GIT_CONFIG_VALUE_0=AUTHORIZATION: basic <base64(x-access-token:***)>'
        Write-Plan '    GIT_TERMINAL_PROMPT=0'
        Write-Info 'the token is never written to .git/config, the remote URL, argv, or any file'
    } else {
        $remoteResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'remote', 'get-url', 'origin')
        $originExists = ($remoteResult.ExitCode -eq 0)
        if ($originExists) {
            $previousOrigin = $remoteResult.Output.Trim()
            $setUrlResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'remote', 'set-url', 'origin', $originUrl)
            if ($setUrlResult.ExitCode -ne 0) {
                Stop-Publish -MessageLines @(
                    'Could not update the origin remote URL.',
                    ('git said: ' + (Redact $setUrlResult.Output))
                )
            }
            Write-Ok ('updated origin to ' + $originUrl)
            if ($previousOrigin -ne $originUrl) {
                Write-Info ('previous origin was: ' + $previousOrigin)
            }
        } else {
            $addRemoteResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'remote', 'add', 'origin', $originUrl)
            if ($addRemoteResult.ExitCode -ne 0) {
                Stop-Publish -MessageLines @(
                    'Could not add the origin remote.',
                    ('git said: ' + (Redact $addRemoteResult.Output))
                )
            }
            Write-Ok ('added origin ' + $originUrl)
        }

        Set-GitAuthEnvironment -BasicCredential $basicCredential
        Write-Info 'pushing main with an ephemeral process-scoped Authorization header (token never in argv or the URL)'
        try {
            $pushResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'push', '-u', 'origin', $script:BranchName)
        } finally {
            Restore-ProcessEnvironment
        }

        if ($pushResult.ExitCode -ne 0) {
            $safePushOutput = Redact $pushResult.Output
            $pushFailureLines = New-Object System.Collections.Generic.List[string]
            $pushFailureLines.Add('git push failed with exit code ' + $pushResult.ExitCode + '.')
            if (-not [string]::IsNullOrWhiteSpace($safePushOutput)) {
                $pushFailureLines.Add('git said: ' + $safePushOutput)
            }
            foreach ($pushHint in (Get-PushFailureHints -OutputText $safePushOutput)) {
                $pushFailureLines.Add('hint: ' + $pushHint)
            }
            Stop-Publish -MessageLines ($pushFailureLines.ToArray())
        }

        Write-Ok ('pushed ' + $script:BranchName + ' to ' + $originUrl)
    }

    # ------------------------------------------------------------------
    # [6/7] Verify
    # ------------------------------------------------------------------
    Write-Section '[6/7] Verify'

    if (-not $isExecute) {
        Write-Plan 'read-only checks that the real run performs after pushing:'
        Write-Plan (Format-GitCommand -GitArguments @('-C', $script:ResolvedRepoRoot, 'remote', 'get-url', 'origin'))
        if ($repoExists -or $headExists) {
            Write-Plan (Format-GitCommand -GitArguments @('-C', $script:ResolvedRepoRoot, 'rev-parse', '--short', 'HEAD'))
        }
        Write-Info 'the persisted origin URL must contain no credentials; the script resets it if it ever does'
    } else {
        $verifyRemoteResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'remote', 'get-url', 'origin')
        if ($verifyRemoteResult.ExitCode -ne 0) {
            Stop-Publish -MessageLines @(
                'Could not read the origin URL after the push.',
                ('git said: ' + (Redact $verifyRemoteResult.Output))
            )
        }
        $persistedOrigin = $verifyRemoteResult.Output.Trim()
        $originHasCredential = [regex]::IsMatch($persistedOrigin, '^[A-Za-z][A-Za-z0-9+.-]*://[^/]*@')
        if ($originHasCredential) {
            $resetResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'remote', 'set-url', 'origin', $originUrl)
            if ($resetResult.ExitCode -ne 0) {
                Stop-Publish -MessageLines @(
                    'The origin URL contained embedded credentials and could not be reset.',
                    ('git said: ' + (Redact $resetResult.Output))
                )
            }
            Write-Warn ('origin URL contained embedded credentials; reset to ' + $originUrl)
        } else {
            Write-Ok ('origin URL contains no credentials: ' + $persistedOrigin)
        }
        $finalHeadFull = Get-GitHeadHash -RootPath $script:ResolvedRepoRoot
        $finalHeadShort = Get-GitHeadHash -RootPath $script:ResolvedRepoRoot -Short
        $finalBranch = ''
        $finalBranchResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'rev-parse', '--abbrev-ref', 'HEAD')
        if ($finalBranchResult.ExitCode -eq 0) {
            $finalBranch = $finalBranchResult.Output.Trim()
        }
        Write-Ok ('local HEAD is ' + $finalHeadShort + ' on ' + (Get-DisplayValue $finalBranch))
        $statusAfterResult = Invoke-Git -GitArguments @('-C', $script:ResolvedRepoRoot, 'status', '--porcelain')
        if ($statusAfterResult.ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($statusAfterResult.Output)) {
            Write-Warn 'working tree still has uncommitted changes after the publish (they were not included)'
        }
    }

    # ------------------------------------------------------------------
    # [7/7] Summary
    # ------------------------------------------------------------------
    Write-Section '[7/7] Summary'

    $summaryHeadFull = ''
    $summaryHeadShort = ''
    if ($isExecute) {
        $summaryHeadFull = Get-GitHeadHash -RootPath $script:ResolvedRepoRoot
        $summaryHeadShort = Get-GitHeadHash -RootPath $script:ResolvedRepoRoot -Short
    } else {
        $summaryHeadFull = $currentHeadFull
        $summaryHeadShort = $currentHeadShort
    }

    $pagesUrl = 'https://' + $UserName.ToLowerInvariant() + '.github.io/' + $RepoName + '/'
    Write-Host ('  Repository : ' + $repoUrl)
    Write-Host ('  Branch     : ' + $script:BranchName)
    if (-not [string]::IsNullOrWhiteSpace($summaryHeadShort)) {
        Write-Host ('  HEAD       : ' + $summaryHeadShort)
        Write-Host ('  Commit URL : ' + $repoUrl + '/commit/' + $summaryHeadFull)
    } else {
        Write-Host '  HEAD       : (no commit yet; the publish creates the first commit on main)'
    }
    Write-Host ('  Pages URL  : ' + $pagesUrl + '  (available only after enabling GitHub Pages)')
    Write-Host '  Next       : see docs/PUBLISHING.md for topics, the v0.1.0 release, and optional Pages setup'

    if (-not $isExecute) {
        Write-Host ''
        Write-Host '  This was a dry run: nothing was changed and nothing was pushed.' -ForegroundColor Yellow
        Write-Host '  Re-run with -Execute (and GITHUB_TOKEN set) to publish.' -ForegroundColor Yellow
    } else {
        Write-Host ''
        Write-Host '  Publish complete.' -ForegroundColor Green
    }
} catch {
    if (-not $script:HandledFatal) {
        Write-ErrorLine ('Unexpected failure: ' + (Redact $_.Exception.Message))
        try {
            $positionMessage = [string]$_.InvocationInfo.PositionMessage
            if (-not [string]::IsNullOrWhiteSpace($positionMessage)) {
                Write-ErrorLine ('Location: ' + (Redact ($positionMessage -replace '\s+', ' ')))
            }
        } catch {
            Write-ErrorLine 'Location: unavailable'
        }
    }
    $script:ExitCode = 1
} finally {
    Restore-ProcessEnvironment
}

exit $script:ExitCode
