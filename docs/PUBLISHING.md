# Publishing FailBench to GitHub

This is the operator runbook for taking the FailBench repository - a local
clone of this project, referred to below as `<repo-root>` - to GitHub from
Windows with PowerShell 7. It covers the one-time account and token setup, the
safe dry-run/execute publish flow, post-publish verification and metadata, the
v0.1.0 release, optional GitHub Pages hosting, updates, and troubleshooting.

- Repository root: `<repo-root>` - the folder that contains `pyproject.toml`
  (also the folder containing the `scripts` folder you run the commands from)
- Shell: PowerShell 7 (`pwsh`), Windows 10 or 11
- Git: portable build at `_scratch\Git\bin\git.exe` (git 2.56.1)
- Publish tooling: `scripts\publish\publish.ps1` and
  `scripts\publish\make_archive.ps1`

**Placeholders.** Values in angle brackets such as `<repo-root>`,
`<github-user>`, `<your-email>`, and `<repo-name>` are intentional user inputs.
Replace them with your own values before you run a command; they are never
filled in by the scripts. For `<repo-root>`, use the absolute path of your
clone (for example `C:\work\llm-failbench` or `D:\src\llm-failbench`).
PowerShell treats `<` and `>` as redirection operators, so an unreplaced
placeholder outside quotes makes the command fail to parse; inside quotes it
stays a literal string and the command fails visibly (for example
`Set-Location` reports a missing directory). Either way a placeholder is never
silently replaced with a guessed value.

The scripts do not create accounts, do not request tokens on your behalf,
and do not publish anywhere except the repository you name. Every account
action in this guide is performed by you in a browser.

---

## 1. Overview

### 1.1 What gets published

The first push publishes the repository content exactly as tracked by git:

| Area | Contents |
|---|---|
| `failbench/` | Standard-library runner, scoring, providers, CLI, report, gate |
| `probes/` | Deterministic probe JSON, one file per probe, grouped by failure class |
| `data/evidence/` | Cited evidence atlas (JSONL per class plus `index.json`) |
| `results/demo/` | The committed deterministic mock demo run (`results.json`, `raw.jsonl`) |
| `site/index.html` | Self-contained static dashboard and atlas (no build step) |
| `docs/` | Contract, quickstart, methodology, taxonomy, atlas, results, roadmap, FAQ, this guide |
| `.github/` | CI workflow, issue forms, pull-request template |
| `tests/` | Offline unit tests |
| Root files | `README.md`, `LICENSE` (MIT), `CITATION.cff`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`, `pyproject.toml`, `.gitignore` |

Everything else stays out of the public repository: `_scratch/` is
gitignored (portable git, downloaded tools, local test output), and raw
results under `results/` are gitignored except `results/demo/`. The
`make_archive.ps1` builder also excludes `_scratch`, `__pycache__`, `*.pyc`,
virtual environments, `node_modules`, `*.zip`, and raw results by policy.

### 1.2 What the scripts do

`scripts\publish\publish.ps1` is the publish driver. It runs seven printed
phases: [1/7] Environment (repo root, target repository, visibility, commit
identity, token status), [2/7] Repo state (reuse or initialize `.git`, set the
local commit identity when it is missing or different, force branch `main`),
[3/7] Commit (`git add -A`, skip the commit when nothing changed, refuse to
publish a repository with no commits and nothing staged), [4/7] GitHub repo
(read-only existence check, then create with `POST /user/repos` only when
missing; `201` created, `422` already exists continues idempotently, `401` and
`403` stop with fix hints), [5/7] Push (set the credential-free origin URL,
push `main` with process-scoped credentials, restore the environment), [6/7]
Verify (origin URL has no credentials, local HEAD, working-tree warning), and
[7/7] Summary (repository URL, branch, HEAD, commit URL, Pages URL, next
step). The default mode is a dry run that prints every git command and every
HTTP request as `[PLAN]` lines and makes no file writes and no network calls.
It reads the token only for `-Execute`, never prints or persists it, and is
safe to re-run.

`scripts\publish\make_archive.ps1` builds the optional release artifacts in
`_scratch\dist\`: `failbench-v0.1.0.zip` (source archive of tracked files),
`failbench-v0.1.0.bundle` (portable git bundle of all refs, only when the
repository has commits), and `SHA256SUMS.txt`. It refuses to archive and
exits with code 2 if it finds high-confidence secret material, so it doubles
as a pre-publish secret check.

### 1.3 Safety properties

| Property | How it works | What you can verify |
|---|---|---|
| Dry run by default | Without `-Execute` the script prints the plan as `[PLAN]` lines: it modifies no files, runs no writing git commands, and makes no network calls | The banner says `MODE: DRY RUN (no changes, no network writes)`; exit code 0 |
| Token from environment only | The script reads `$env:GITHUB_TOKEN` (trimmed), never prompts for it, never accepts it as a parameter; a dry run works without a token, `-Execute` stops with a fix list if the token is missing | `[1/7] Environment` prints `GITHUB_TOKEN : present (value never shown)` |
| Token never written to disk or printed | The push supplies the Authorization header through a per-process git config environment (`GIT_CONFIG_COUNT=1`, `GIT_CONFIG_KEY_0=http.https://github.com/.extraheader`, `GIT_CONFIG_VALUE_0=AUTHORIZATION: basic <base64(x-access-token:...)`) plus `GIT_TERMINAL_PROMPT=0`; the variables are removed after the push and output is passed through a redaction helper, so the token/base64 is never in argv, `.git/config`, or the remote URL | `git remote -v` shows a plain `https://github.com/...` URL; `.git/config` has no header or token; the plan prints `***` placeholders |
| Idempotent | A read-only `GET /repos/{owner}/{repo}` pre-check reuses an existing repository (`200`), creates it only when missing (`404` then `201`), and treats `422 already exists` as a warning and continues; the commit step skips when the staged diff is empty; the push is a normal fast-forward update | Run the same command twice; the second run reports the repository exists and nothing new to commit |
| Repository creation through the REST API | `POST /user/repos` with the explicit name, description, private flag, `has_issues=true`, `has_wiki=false`, `has_projects=false`, `auto_init=false` | The dry-run plan prints the exact request body and URL |
| No account creation, no extra publishing | The scripts only create/update the named repository and push `main`; no other remote or account action exists | Dry-run plan lists no other targets |
| No destructive git operations | No force push, no history rewrite, no tag rewriting; a stale credentialed origin URL is detected and reset to the credential-free URL in `[6/7] Verify` | The plan contains no `--force` push |
| Refuses empty publishes | If the repository has no commits and nothing is staged, the script stops instead of pushing an empty repository | The `[3/7] Commit` phase reports the refusal |
| Secret guard for artifacts | `make_archive.ps1` scans candidate files and refuses on token-shaped content (the publish script itself does not scan; run the archive guard first) | Exit code 2 with a finding list means "do not publish until resolved" |

### 1.4 Preconditions checklist

- [ ] Windows 10/11, PowerShell 7 installed, terminal in the repository root
- [ ] Portable git present at `_scratch\Git\bin\git.exe`
- [ ] All repository files complete (README, LICENSE, CITATION, CHANGELOG,
      probes, evidence, demo results, site dashboard, CI workflow, publish scripts)
- [ ] Secret scan clean
- [ ] Offline tests and strict validation green
- [ ] GitHub account created, email verified, 2FA enabled (Steps 1-3)
- [ ] Classic PAT with `repo` and `workflow` scopes in `$env:GITHUB_TOKEN`
- [ ] Dry run completed successfully and its command plan reviewed

Steps 0-3 prepare those preconditions; Steps 4-10 publish, verify, and finish
the repository metadata.

---

## 2. Step 0 - Prerequisites

Run these commands from the repository root in PowerShell 7. If
`Get-Location` does not print your clone directory (the folder that contains
`pyproject.toml`), change directory first:

```powershell
Set-Location '<repo-root>'
Get-Location
```

Replace `'<repo-root>'` with the absolute path of your clone before running
it, for example `Set-Location 'C:\work\llm-failbench'`. Relative paths
throughout this guide (such as `.\scripts\publish\publish.ps1`,
`.\_scratch\Git\bin\git.exe`, and `.\site\index.html`) are resolved from
whatever directory you are in, so they work for any clone location.

### 2.1 Install PowerShell 7

```powershell
winget install --id Microsoft.PowerShell --source winget
pwsh -v
```

Expected: `PowerShell 7.x.y`. If `winget` is unavailable, install from the
official PowerShell releases page (https://github.com/PowerShell/PowerShell/releases)
and reopen the terminal. Every command in this guide that invokes a script
uses `pwsh -NoProfile -File`, so the publish flow does not depend on your
PowerShell profile or on `Set-ExecutionPolicy` in the persistent scope.

### 2.2 Verify the portable git

```powershell
& .\_scratch\Git\bin\git.exe --version
```

Expected: `git version 2.56.1.windows.1`. If the file is missing, pass
`-GitPath` with the path to another git executable, or set
`$env:FAILBENCH_GIT` to it for the current session. Both publish scripts
accept `-GitPath`; `make_archive.ps1` also resolves `$env:FAILBENCH_GIT`.

### 2.3 Verify there are no secrets in the working tree

```powershell
Get-ChildItem -Path . -Recurse -File -Force |
    Where-Object { $_.FullName -notlike '*\_scratch\*' -and $_.FullName -notlike '*\.git\*' -and $_.FullName -notlike '*\docs\PUBLISHING.md' } |
    Select-String -Pattern 'ghp_[A-Za-z0-9]{36}','github_pat_[A-Za-z0-9_]{20,}','-----BEGIN [A-Z ]*PRIVATE KEY-----'
```

Expected: no output. The commands are anchored to real token shapes rather
than the bare prefixes, and `docs\PUBLISHING.md` is excluded on purpose
because this guide documents the patterns themselves - scanning it would
always produce false positives. Any hit in a real file is a stop condition:
remove the secret, rotate it if it was ever real, and only then continue.
The `_scratch` folder is skipped because it contains downloaded tools; it is
gitignored and never published.

The archive builder runs the authoritative version of this check
automatically, with additional filename and content rules (`.env`, `*.pem`,
AWS keys, Slack tokens, OpenAI-style keys, and more):

```powershell
pwsh -NoProfile -File .\scripts\publish\make_archive.ps1 -SkipBundle
```

Expected: `[OK] secret scan: clean` followed by `[OK] source zip: ...` and
exit code 0. Exit code 2 means secret-like content was found and the script
refused to archive - read the reported file:line list, fix it, and re-run.
This step also proves the archive pipeline works before you publish anything.
Delete `_scratch\dist` afterwards if you do not want the artifacts yet (it is
gitignored either way).

### 2.4 Confirm tests and validation pass

```powershell
python -m unittest discover -s tests -t . -v
python -m failbench validate --strict
```

Expected: the test run ends in `OK` with no failures or errors, and the
strict validation exits 0 with no errors. Do not publish on a red test run.
Both commands are offline: they need no network and no API key.

### 2.5 Confirm the publishable file set is complete

```powershell
$required = @(
    'README.md',
    'LICENSE',
    'CITATION.cff',
    'CHANGELOG.md',
    'pyproject.toml',
    'site\index.html',
    'docs\QUICKSTART.md',
    'docs\METHODOLOGY.md',
    'docs\RESULTS.md',
    'docs\CONTRACT.md',
    '.github\workflows\ci.yml',
    'results\demo\results.json',
    'scripts\publish\publish.ps1',
    'scripts\publish\make_archive.ps1'
)
foreach ($path in $required) { '{0,-40} {1}' -f $path, (Test-Path -LiteralPath $path) }
```

Expected: every line ends in `True`. The docs, README, CHANGELOG, demo
results, and site dashboard are generated by the build; at publish time they
must all exist and be committed-ready. A `False` means the build is not
finished - publish later rather than publishing an incomplete repository.

---

## 3. Step 1 - Create the GitHub account

You need a GitHub account that will own the repository. The account name
becomes `<github-user>` in every URL and command below. No organization is
needed; a personal account is enough for a public open-source project.

1. Open https://github.com/signup and create an account with an email address
   you control. The account-creation procedure is documented at
   https://docs.github.com/en/account-and-profile/how-tos/account-management/creating-an-account-on-github
2. Verify the email address. This is not optional for publishing: an
   unverified address cannot create repositories or generate personal access
   tokens (see the GitHub email reference:
   https://docs.github.com/en/account-and-profile/reference/email-addresses-reference).
3. Enable two-factor authentication: **Settings -> Password and
   authentication -> Enable two-factor authentication**. As of March 2023
   GitHub requires 2FA for users who contribute code on GitHub.com
   (eligibility-based rollout; enabling it is strongly recommended for any
   account that owns a public repository). Steps and recovery codes:
   https://docs.github.com/en/authentication/securing-your-account-with-two-factor-authentication-2fa/configuring-two-factor-authentication
   and
   https://docs.github.com/en/authentication/securing-your-account-with-two-factor-authentication-2fa/about-mandatory-two-factor-authentication
4. Decide the commit email address. Open **Settings -> Emails**. Either use
   your real email address (commits are attributed to your account and show
   the address in the commit metadata) or enable **Keep my email addresses
   private** and use the GitHub-provided noreply address of the form
   `ID+USERNAME@users.noreply.github.com` (privacy-preserving; GitHub maps it
   back to your account). The format and the privacy behavior are documented
   at
   https://docs.github.com/en/account-and-profile/reference/email-addresses-reference
   and
   https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address.
   Whichever you choose, pass it as `-UserEmail` in Steps 4-5, because the
   publish script authors the commit with exactly that identity.
5. Note the username. That is the `<github-user>` value used in the rest of
   this guide, for example `https://github.com/<github-user>/llm-failbench`.

Recommended account settings for a repository owner: keep 2FA recovery codes
in a password manager, add a backup email, and do not reuse the account
password anywhere else. The scripts never log in to the account and never
create it.

---

## 4. Step 2 - Create a personal access token

The publish script authenticates to the GitHub REST API and to git over HTTPS
with a single token read from `$env:GITHUB_TOKEN`. A classic personal access
token (PAT) with the `repo` and `workflow` scopes is the supported path.

### 4.1 Create a classic token (recommended)

1. Open https://github.com/settings/tokens (or navigate **Settings ->
   Developer settings -> Personal access tokens -> Tokens (classic)**).
2. Choose **Generate new token (classic)**.
3. Name it something explicit, for example `failbench-publish`, and set an
   expiration such as 30-90 days. GitHub removes tokens that have not been
   used for a year and strongly recommends expirations; see
   https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
4. Select scopes:
   - `repo` - required to create the repository, push commits, set repository
     metadata, and create the release. This is the full "Full control of
     private repositories" scope.
   - `workflow` - **required**, because this repository contains
     `.github/workflows/ci.yml`. Without this scope git rejects the push with
     an error in the form:
     `refusing to allow a Personal Access Token to create or update workflow '.github/workflows/ci.yml' without 'workflow' scope`.
     The fix is to edit the token (or generate a new one) and grant the
     `workflow` scope; a push that only adds the workflow file will be
     rejected until then.
5. Generate the token and copy it once. GitHub shows the value only at
   creation time. Treat it like a password.

Select nothing else. `repo` plus `workflow` is enough for everything in this
guide. Avoid broad scopes such as `admin:org`, `delete_repo`, or `gist`; they
are not needed and increase the impact of a leak.

Token documentation, scope lists, and the "classic vs fine-grained" guidance:
https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens

### 4.2 Fine-grained tokens (alternative, with caveats)

GitHub recommends fine-grained PATs where they work, but this workflow was
built and tested against a classic token. Fine-grained tokens are limited to
one owner and to explicitly selected repositories, and GitHub documents that
they cannot do everything classic tokens can:
https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens

If you use one anyway, grant at least **Contents: Read and write** for the
target repository, plus the repository permissions the individual REST
endpoints require (**Metadata: Read**, and administration-level permission for
repository creation). Creating a new user-owned repository through
`POST /user/repos` with a fine-grained token is not the same well-trodden path
as with a classic token and may be rejected; endpoint availability for
fine-grained tokens is listed at
https://docs.github.com/en/rest/authentication/endpoints-available-for-fine-grained-personal-access-tokens.
If creation or push fails with a permission error and you have a classic
token available, switch to classic rather than fighting the scope matrix.
Fine-grained tokens expire and can be granted per repository, which is a real
security advantage for long-lived use.

### 4.3 GitHub CLI (optional alternative, not used by the scripts)

If you prefer, the GitHub CLI can create the repository and store credentials:
`gh auth login`, then
`gh repo create <repo-name> --public --source . --remote origin --push`.
This is documented at
https://docs.github.com/en/github-cli/github-cli/about-github-cli. The publish
scripts deliberately do **not** use `gh` and do not read its credential store;
they only read `$env:GITHUB_TOKEN`. Do not mix the two paths for the same
first push: pick one.

Note that `gh` stores its credential in the operating-system credential store,
while the publish script keeps the token in process memory and a per-process
git header only. The rest of this guide assumes the token-in-environment path.

---

## 5. Step 3 - Set the token in the current PowerShell session

The token must reach the publish script through the environment. Set it in the
same terminal that runs the script; child processes inherit it, which is
exactly how `publish.ps1` receives it.

### 5.1 Masked prompt (PowerShell 7)

```powershell
$env:GITHUB_TOKEN = Read-Host -MaskInput 'Paste GitHub PAT'
```

`-MaskInput` is a PowerShell 7 feature: the pasted value is not echoed to the
terminal (it still goes into the environment variable of this process only).
If `-MaskInput` is not recognized you are running Windows PowerShell 5.1;
switch to PowerShell 7 with the `pwsh` command, or use the fallback below.

### 5.2 Fallback for Windows PowerShell 5.1

```powershell
$secure = Read-Host -AsSecureString 'Paste GitHub PAT'
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $env:GITHUB_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
```

The `finally` block frees the unmanaged memory that holds the plain-text
token; never skip it.

### 5.3 Verify the token is set without printing it

```powershell
if ([string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) {
    'MISSING'
}
else {
    'set, length ' + $env:GITHUB_TOKEN.Length
}
```

Expected: `set, length 40` for a classic token (a classic token is 40
characters). This check prints only the length; never print the token value
itself, not even with `Write-Host $env:GITHUB_TOKEN`.

Session rules:

- The variable lives only in this PowerShell process (and its children). A new
  terminal starts without it; repeat this step there.
- Never put the token in a file, a PowerShell profile, a shell history line,
  an issue, a commit, a script, or a chat message.
- Never type the token as a command argument; masked `Read-Host` input keeps
  it out of the console and out of `Get-History` command lines.
- When you are done publishing for the day, clear it:
  `Remove-Item Env:GITHUB_TOKEN`

---

## 6. Step 4 - Dry run (default, safe)

The publish script is a dry run unless `-Execute` is passed. It validates the
parameters, resolves git and the repository root, inspects the local
repository, prints the REST request it would make and the exact git command
plan, and exits 0 without touching GitHub.

Run this from the repository root with the placeholder values replaced:

```powershell
pwsh -NoProfile -File .\scripts\publish\publish.ps1 -UserName <github-user> -UserEmail <your-email> -Description "The evidence-backed, judge-free failure probe kit for LLMs."
```

Options relevant here:

- `-UserName` - the GitHub account that will own the repository
  (`<github-user>`). Required; validated as a GitHub login (1-39 letters,
  digits, or hyphens, starting with a letter or digit). An organization handle
  also works.
- `-RepoName` - repository name, default `llm-failbench`. Must be 1-100
  characters of letters, digits, dot, underscore, or hyphen and must not be
  `.` or `..`. Only change it if the repository must be named differently; the
  README and CFF assume `llm-failbench`.
- `-UserEmail` - the commit author email chosen in Step 1. Optional; when
  omitted the script uses the noreply form
  `<github-user>@users.noreply.github.com` and warns about it. It must contain
  `@` and no whitespace.
- `-Description` - repository description. Optional; the default is the
  project tagline. Maximum 350 characters (the GitHub API limit).
- `-Private` - create the repository as private instead of public. Public is
  expected for this OSS project; private changes what GitHub Pages can do on
  a free plan (Step 9).
- `-GitPath` - optional path to `git.exe` or to the `bin` directory that
  contains it, if the portable git is not at the default location.
- `-RepoRoot` - optional advanced override for the repository root. The
  default is the checkout that contains the script (two levels above
  `scripts\publish`), so normally you do not pass it.

The dry-run output is a phase log, and every planned action is a `[PLAN]`
line you can read before anything happens:

1. `MODE: DRY RUN (no changes, no network writes)` banner.
2. `[1/7] Environment` - repository root, target repository, visibility,
   commit identity, and `GITHUB_TOKEN : present (value never shown)` or
   `not set - required for -Execute`. A dry run works without a token; only
   `-Execute` requires one.
3. `[2/7] Repo state` - whether `.git` exists (and is reused), current HEAD
   and branch, the planned `git init -b main` when `.git` is missing (with
   the note "dry run: no .git directory was created"), and the planned local
   `user.name` / `user.email` configuration (only written when missing or
   different).
4. `[3/7] Commit` - `git add -A`, a read-only `git status` summary (untracked
   and modified counts, file count under `.gitignore` rules), the planned
   commit message `release: failbench v0.1.0`, and whether the real run would
   create a commit, find nothing to commit, or create the first commit.
5. `[4/7] GitHub repo` - the read-only existence `GET`, the `POST
   /user/repos` creation plan (only when the repository does not exist), the
   request headers with `Authorization: Bearer ***`, and the exact JSON
   request body.
6. `[5/7] Push` - the planned `remote set-url origin` (or `remote add
   origin`), `push -u origin main`, and the per-process environment variables
   used for authentication, with the credential shown only as
   `AUTHORIZATION: basic <base64(x-access-token:***)>`. The
   `http.extraheader` value is supplied through that process-only git config
   environment, so the token and its base64 never enter argv, `.git/config`,
   or the remote URL, and the environment is removed after the push.
7. `[6/7] Verify` - read-only checks the real run performs: `remote get-url
   origin` and `rev-parse --short HEAD`.
8. `[7/7] Summary` - `Repository`, `Branch`, `HEAD`, `Commit URL`, and
   `Pages URL` (`https://<github-user>.github.io/<repo-name>/`, marked as
   available only after enabling GitHub Pages), followed by the line "This
   was a dry run: nothing was changed and nothing was pushed."

How to read the git command plan:

- Every planned git command is printed with its full argument vector, in
  execution order: `git init` (only when `.git` is missing), the local
  `config user.name` / `user.email` writes, `git add -A`, the commit with
  `-m release: failbench v0.1.0`, `remote set-url`/`add origin` with the
  plain `https://github.com/...` URL, and `push -u origin main`.
- Nothing in the plan is executed in a dry run, and the dry run makes no
  network calls. Confirm the plan contains no `--force` and that the origin
  URL contains no token.
- Exit code 0 means the plan is coherent. A non-zero exit means an input or
  environment problem - fix it before touching `-Execute`. Typical causes are
  an invalid `-UserName` or `-RepoName`, an over-long `-Description`, a
  missing token with `-Execute`, a wrong working directory, or git not found.
  Validation failures print `Invalid arguments; nothing was changed:` and no
  git or network command is run.

If you have not created the token yet, you can already run the dry run: it
prints `GITHUB_TOKEN : not set - required for -Execute` and continues,
because only the real run needs the token.

---

## 7. Step 5 - Execute the first publish

When the dry run is clean, repeat the same command with `-Execute`:

```powershell
pwsh -NoProfile -File .\scripts\publish\publish.ps1 -UserName <github-user> -UserEmail <your-email> -Description "The evidence-backed, judge-free failure probe kit for LLMs." -Execute
```

Expected phases and outcomes, in order, matching the seven printed phases:

1. `MODE: EXECUTE` banner, then `[1/7] Environment`: repository root, target
   repository URL, visibility, commit identity, and token status
   (`present (value never shown)`). If `-UserEmail` was omitted, a warning
   shows the noreply address that will be used.
2. `[2/7] Repo state`: an existing `.git` is reused; otherwise the repository
   is initialized with `git init -b main` (or `git init` plus a branch rename
   on older git). The local `user.name` / `user.email` are written only when
   missing or different, and the branch is forced to `main`.
3. `[3/7] Commit`: `git add -A` stages the working tree (respecting
   `.gitignore`); if there is a staged diff it is committed as
   `release: failbench v0.1.0`, otherwise the phase reports "nothing new to
   commit (working tree clean)". If the repository has no commits and nothing
   is staged, the script refuses to publish an empty repository.
4. `[4/7] GitHub repo`: a read-only `GET /repos/{owner}/{repo}` pre-check.
   `404` means "does not exist yet" and the script creates it with
   `POST /user/repos`; `201` means created and `422` means it already exists
   (the script warns and continues idempotently; this is the safe path).
   `401` and `403` stop the run with concrete fix instructions and no push.
   The repository is created with `has_issues=true`, `has_wiki=false`,
   `has_projects=false`, and `auto_init=false`, so the local `main` pushes
   cleanly without a remote README.
5. `[5/7] Push`: `origin` is added, or `set-url`-ed, to
   `https://github.com/<github-user>/<repo-name>.git` (credential-free URL);
   then `push -u origin main` runs with the ephemeral process-scoped
   credential environment variables, which are restored afterwards.
6. `[6/7] Verify`: the persisted origin URL is checked for embedded
   credentials (and reset if one was found), the local HEAD is printed, and
   uncommitted leftovers are reported.
7. `[7/7] Summary`: `Repository`, `Branch`, `HEAD`, `Commit URL`, and
   `Pages URL` (`https://<github-user>.github.io/<repo-name>/`, marked as
   available only after enabling GitHub Pages), then "Publish complete."

The whole run normally takes about 10-60 seconds on a normal connection; the
first push of the full tree can take a little longer. If it stops, read the
last `[ERROR]` line and its hint, fix the reported issue, and re-run the same
command - the script is idempotent and safe to retry.

Re-run the same command (copy-pasteable) to confirm idempotency:

```powershell
pwsh -NoProfile -File .\scripts\publish\publish.ps1 -UserName <github-user> -UserEmail <your-email> -Description "The evidence-backed, judge-free failure probe kit for LLMs." -Execute
```

Expected on the second run: `[4/7]` reports
`repository already exists, continuing (idempotent)`, `[3/7]` reports
`nothing new to commit (working tree clean)` when nothing changed, and
`[5/7]` pushes an already up-to-date `main`. Exit code 0.

### 7.1 Manual fallback

Use this only if the script cannot complete a step and you need to publish
by hand. It performs the same actions; keep the token in `$env:GITHUB_TOKEN`
and never paste it into a URL.

```powershell
$githubUser = '<github-user>'
$userEmail  = '<your-email>'
$repoName   = 'llm-failbench'
```

Initialize and commit (skip `git init` if `.git` already exists):

```powershell
& .\_scratch\Git\bin\git.exe init -b main
& .\_scratch\Git\bin\git.exe add -A
& .\_scratch\Git\bin\git.exe -c user.name="$githubUser" -c user.email="$userEmail" commit -m "release: failbench v0.1.0"
```

Create the repository through the REST API (or use the GitHub web UI: **New
repository**, empty, no README, no license, no .gitignore):

```powershell
$headers = @{
    'User-Agent'    = 'failbench-manual-publish'
    'Authorization' = "Bearer $env:GITHUB_TOKEN"
    'Accept'        = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
}
$createBody = @{
    name         = $repoName
    description  = 'The evidence-backed, judge-free failure probe kit for LLMs.'
    private      = $false
    has_issues   = $true
    has_wiki     = $false
    has_projects = $false
    auto_init    = $false
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'https://api.github.com/user/repos' -Headers $headers -Body $createBody -ContentType 'application/json' |
    Select-Object html_url, visibility, default_branch
```

This is the same payload the publish script sends. `auto_init = $false` is
important: an automatically initialized README would put a commit on the
remote that your local `main` does not have, and the first push would be
rejected as non-fast-forward.

Set the remote and push with a per-process credential header:

```powershell
& .\_scratch\Git\bin\git.exe remote add origin "https://github.com/$githubUser/$repoName.git"
$env:GIT_TERMINAL_PROMPT = '0'
$basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('x-access-token:' + $env:GITHUB_TOKEN))
& .\_scratch\Git\bin\git.exe -c credential.helper= -c "http.extraheader=AUTHORIZATION: basic $basic" push -u origin main
```

If `origin` already exists, use
`& .\_scratch\Git\bin\git.exe remote set-url origin "https://github.com/$githubUser/$repoName.git"`
instead of `remote add`. The base64 value is derived from the token in memory
for this one command; it is not written to `.git/config`, and
`credential.helper=` prevents any credential manager from being consulted or
populated.

---

## 8. Step 6 - Verify the publish

The publish script's `[7/7] Summary` already printed the repository URL, the
branch, the local HEAD, the commit URL, and the Pages URL placeholder. The
commands below re-confirm the same facts from the local checkout and from the
GitHub API.

### 8.1 Local checks

```powershell
& .\_scratch\Git\bin\git.exe remote -v
& .\_scratch\Git\bin\git.exe log --oneline -1
& .\_scratch\Git\bin\git.exe status -sb
```

Expected: `origin` points at
`https://github.com/<github-user>/llm-failbench.git` (fetch and push) with no
embedded credentials; the top commit is the release commit; the branch shows
`## main...origin/main` with a clean working tree.

### 8.2 Browser checks

Open `https://github.com/<github-user>/llm-failbench` and confirm:

- The landing page renders `README.md` (README is the repository homepage).
- The license is detected as MIT (license badge or `MIT license` label).
- The latest commit message and time match what the script printed.
- The **Actions** tab lists the CI workflow and a run triggered by the push.
  A red run is a stop sign: inspect the failing job before announcing the
  release.
- The **Issues** tab is present and **Discussions** is visible only if you
  enable it in Step 7.

### 8.3 REST checks

```powershell
$githubUser = '<github-user>'
$repoName   = 'llm-failbench'
$headers = @{
    'User-Agent'    = 'failbench-publish-check'
    'Authorization' = "Bearer $env:GITHUB_TOKEN"
}
$repo = Invoke-RestMethod -Uri "https://api.github.com/repos/$githubUser/$repoName" -Headers $headers
$repo.html_url
$repo.visibility
$repo.default_branch
```

Expected: `https://github.com/<github-user>/llm-failbench`, `public` (or
`private` if you passed `-Private`), and `main`. Do not pipe the full
response object to a shared log or chat: print only the fields you need and
never print `$headers`. If the repository is private and a request is
unauthenticated, the API returns `404` rather than `403` - that is expected
behavior, not a missing repository.

The REST reference for this endpoint is
https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28#get-a-repository
and the authentication rules are at
https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api?apiVersion=2022-11-28.

---

## 9. Step 7 - Finish repository metadata

### 9.1 Set the description through the REST API

```powershell
$githubUser = '<github-user>'
$repoName   = 'llm-failbench'
$headers = @{
    'User-Agent'    = 'failbench-publish-metadata'
    'Authorization' = "Bearer $env:GITHUB_TOKEN"
    'Accept'        = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
}
$repoBody = @{
    description = 'The evidence-backed, judge-free failure probe kit for LLMs. Deterministic probes, sourced evidence, no LLM judges.'
} | ConvertTo-Json
Invoke-RestMethod -Method Patch -Uri "https://api.github.com/repos/$githubUser/$repoName" -Headers $headers -Body $repoBody -ContentType 'application/json' |
    Select-Object full_name, description, has_issues
```

The endpoint reference is
https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28#update-a-repository.
Equivalent web-UI path: repository page -> **Settings** -> **General** ->
**Description**. Add the Pages URL as **Website** only after Step 9 is live.

### 9.2 Set topics through the REST API

`PUT /repos/{owner}/{repo}/topics` replaces the whole topic list, which is
why the command sends the complete set at once
(https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28#replace-all-repository-topics-for-a-repository).
The 15 topics below were each checked on 2026-11-24: every
`https://github.com/topics/<topic>` page returned HTTP 200 with a populated
topic listing, so none of these are invented slugs.

```powershell
$topics = @(
    'llm',
    'llm-evaluation',
    'model-evaluation',
    'evaluation',
    'benchmark',
    'benchmarking',
    'testing',
    'reproducibility',
    'deterministic',
    'hallucination',
    'ai-safety',
    'prompt-engineering',
    'openai',
    'llmops',
    'github-pages'
)
$topicsBody = @{ names = $topics } | ConvertTo-Json
$result = Invoke-RestMethod -Method Put -Uri "https://api.github.com/repos/$githubUser/$repoName/topics" -Headers $headers -Body $topicsBody -ContentType 'application/json'
$result.names
```

Expected: the call echoes the 15 topic names. Equivalent web-UI path:
repository page -> **About** (gear icon) -> **Topics** -> type each topic and
press Enter -> **Save changes**. Topics are lowercase, hyphenated, and
discoverable search terms; they are not keywords in the README.
Classification guidance:
https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics

### 9.3 Issues, Discussions, social preview

- **Issues** - enabled by default for a new repository; the create call in
  this guide sets `has_issues = $true`. Keep it on: evidence submissions,
  probe requests, and bug reports arrive there.
- **Discussions** (optional) - **Settings -> Features -> Discussions ->
  Set up discussions**. Useful once there is a community; not required for
  v0.1.0. Reference:
  https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/enabling-or-disabling-github-discussions-for-a-repository
- **Social preview** (optional) - **Settings -> General -> Social preview**.
  Use `assets/banner.svg` exported to PNG (or any 1280x640 image) so links to
  the repository render a card on social platforms. Reference:
  https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview

---

## 10. Step 8 - Create the v0.1.0 release

The release is a git tag plus a GitHub release page with notes. The tag must
exist before the release is created when you use the REST API with
`tag_name = v0.1.0`.

### 10.1 Tag and push the tag

```powershell
& .\_scratch\Git\bin\git.exe tag -a v0.1.0 -m "FailBench v0.1.0"
& .\_scratch\Git\bin\git.exe push origin v0.1.0
```

The first publish wrote the local commit identity (`user.name`/`user.email`)
into `.git/config`, so the annotated tag works without extra flags in this
checkout. If you are working in a fresh clone with no identity configured, the
tag command fails with `empty ident name ... not allowed` or
`Please tell me who you are`; pass the identity inline instead:

```powershell
& .\_scratch\Git\bin\git.exe -c user.name="<github-user>" -c user.email="<your-email>" tag -a v0.1.0 -m "FailBench v0.1.0"
```

Pushing the tag needs authentication. After the first publish the remote URL
contains no credentials (that is intentional), and the publish script removed
its ephemeral credential environment when it exited, so the plain
`git push origin v0.1.0` above will prompt (or fail with terminal prompts
disabled) unless a credential helper happens to be configured. If it does not
complete, push with an ephemeral credential the same way the publish script
does:

```powershell
$env:GIT_CONFIG_COUNT = '1'
$env:GIT_CONFIG_KEY_0 = 'http.https://github.com/.extraheader'
$env:GIT_CONFIG_VALUE_0 = 'AUTHORIZATION: basic ' + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('x-access-token:' + $env:GITHUB_TOKEN))
$env:GIT_TERMINAL_PROMPT = '0'
$env:GCM_INTERACTIVE = 'never'
& .\_scratch\Git\bin\git.exe push origin v0.1.0
Remove-Item Env:GIT_CONFIG_COUNT, Env:GIT_CONFIG_KEY_0, Env:GIT_CONFIG_VALUE_0, Env:GIT_TERMINAL_PROMPT, Env:GCM_INTERACTIVE
```

The equivalent one-liner (same credentials, temporary overlay instead of
environment variables) is:

```powershell
$basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('x-access-token:' + $env:GITHUB_TOKEN))
& .\_scratch\Git\bin\git.exe -c credential.helper= -c "http.extraheader=AUTHORIZATION: basic $basic" push origin v0.1.0
```

Expected: `[new tag] v0.1.0 -> v0.1.0`. If the tag already exists on the
remote, the push reports `Everything up-to-date`; that is fine.

### 10.2 Option A - create the release in the web UI

1. Define the release notes in this PowerShell session (this block prints
   them; it does not call the API, so it is safe to run first):

```powershell
$githubUser = '<github-user>'
$repoName   = 'llm-failbench'
$releaseNotes = @'
# FailBench v0.1.0

FailBench is an evidence-backed, judge-free failure probe kit for LLMs. Every
probe is deterministic and every claim is traced to a public source; the kit
uses zero LLM judges and zero third-party Python dependencies.

## What this release contains

- **Evidence atlas** - curated, machine-readable records of publicly reported
  LLM failure modes, each with a real source URL and, where available, a
  popularity signal (Hacker News points/comments, arXiv citations, GitHub
  reactions). The data is CC-BY-4.0.
- **Probe corpus** - 80-120 deterministic probes across ten failure classes:
  hallucination, instruction_following, context_retrieval,
  reasoning_consistency, sycophancy, structured_output, multilingual,
  safety_consistency, agentic_reliability, and determinism_calibration. Each
  probe has exactly one mechanical pass condition.
- **Runner and CLI** - Python standard library only. Run a suite against any
  OpenAI-compatible chat-completions endpoint, replay recorded responses
  offline, and gate a build on regressions.
- **Deterministic mock demo** - a bundled demo run produced by the offline
  mock provider. It is clearly labeled as mock output and is not a
  measurement of any real model.
- **Static dashboard** - `site/index.html`, a single self-contained file with
  inline CSS, JavaScript, and data. No build step and no external assets;
  external links appear only as evidence sources.
- **Offline tests and a CI gate** - the test suite runs with no network and no
  API key, and the shipped workflow validates probes and evidence, runs the
  tests, runs the mock demo, and checks determinism.

## How to run

Run the demo (offline, no API key):

    python -m failbench run --provider mock --demo --out results/demo

Then run the kit against your own OpenAI-compatible endpoint:

    python -m failbench run --provider openai --base-url YOUR_BASE_URL --api-key-env YOUR_KEY_ENV --model YOUR_MODEL --out results/run1

## Honest status

No live model endpoint was available during the build. Every number shipped
in this repository, including `docs/RESULTS.md` and the dashboard demo, was
produced by the deterministic mock provider. FailBench makes no measurement
claims about any production model. Run the kit on your own endpoint to obtain
real numbers.

## Licenses

- Code: MIT (see `LICENSE`).
- Data (evidence and probe corpus): CC-BY-4.0.

## Documentation

- README: https://github.com/GITHUB_OWNER/GITHUB_REPO#readme
- Quickstart: https://github.com/GITHUB_OWNER/GITHUB_REPO/blob/main/docs/QUICKSTART.md
- Methodology: https://github.com/GITHUB_OWNER/GITHUB_REPO/blob/main/docs/METHODOLOGY.md
- Results and caveats: https://github.com/GITHUB_OWNER/GITHUB_REPO/blob/main/docs/RESULTS.md
- Build contract: https://github.com/GITHUB_OWNER/GITHUB_REPO/blob/main/docs/CONTRACT.md

## Contributing

Evidence submissions and probe requests are welcome. Open an issue with the
matching form, include the public source URL and an exact quote for evidence,
and keep payloads harmless. This release does not reproduce jailbreak or
exploit payloads.

Release notes were written by the repository owner. This is an open-source
project announcement, not an endorsement or a claim of adoption.
'@
Write-Output $releaseNotes
```

2. Copy the printed markdown, replacing `GITHUB_OWNER` and `GITHUB_REPO` with
   your account and repository names.
3. Open `https://github.com/<github-user>/llm-failbench/releases`, choose
   **Draft a new release**, select tag `v0.1.0` (created in 10.1), set the
   title `FailBench v0.1.0`, paste the notes, keep **Set as the latest
   release** checked, and publish. Do not attach the `_scratch` artifacts
   unless you built them on purpose (Section 11.4) and want them public.

### 10.3 Option B - create the release through the REST API

Continue in the same PowerShell session (so `$releaseNotes`,
`$githubUser`, and `$repoName` are defined from 10.2):

```powershell
$payload = @{
    tag_name   = 'v0.1.0'
    name       = 'FailBench v0.1.0'
    draft      = $false
    prerelease = $false
    body       = $releaseNotes
} | ConvertTo-Json -Depth 3

# Guard: fail fast if the payload is not valid JSON before sending it.
$null = $payload | ConvertFrom-Json

$headers = @{
    'User-Agent'    = 'failbench-release'
    'Authorization' = "Bearer $env:GITHUB_TOKEN"
    'Accept'        = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
}
$release = Invoke-RestMethod -Method Post -Uri "https://api.github.com/repos/$githubUser/$repoName/releases" -Headers $headers -Body $payload -ContentType 'application/json'
$release.html_url
$release.tag_name
$release.published_at
```

Expected: the printed `html_url` opens the published release, `tag_name` is
`v0.1.0`, and `published_at` is set. `ConvertTo-Json` performs the escaping of
the multi-line markdown body, which is why the body is passed as a normal
PowerShell string rather than hand-written JSON.

The endpoint reference is
https://docs.github.com/en/rest/releases/releases?apiVersion=2022-11-28#create-a-release
and the release-management guide is
https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository

If the release already exists, the API returns `422 Validation Failed` with
`already_exists`. To update its notes instead of failing:

```powershell
$existing = Invoke-RestMethod -Uri "https://api.github.com/repos/$githubUser/$repoName/releases/tags/v0.1.0" -Headers $headers
$updated = Invoke-RestMethod -Method Patch -Uri "https://api.github.com/repos/$githubUser/$repoName/releases/$($existing.id)" -Headers $headers -Body $payload -ContentType 'application/json'
$updated.html_url
```

Verify the rendered notes in the browser: headings, lists, the two indented
code lines, and the honest-status section should all render as markdown.

---

## 11. Step 9 (optional) - Publish the static dashboard with GitHub Pages

`site/index.html` is a single self-contained file: inline CSS, inline
JavaScript, inline data, no build step, no external assets, and external links
only as evidence sources. It is therefore ideal for GitHub Pages. The
complication is structural: branch-based Pages publishing serves either the
repository root (`/`) or a `/docs` folder on the selected branch - never an
arbitrary `site/` folder. So the dashboard needs one of the three options
below. All of them are optional; the repository is complete without Pages.

Whichever option you choose, GitHub Pages for this project is free because
the repository is public. On a private repository, Pages requires GitHub
Pro, GitHub Team, or GitHub Enterprise; the availability statement is in
https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
and the 404 troubleshooting guide is
https://docs.github.com/en/pages/getting-started-with-github-pages/troubleshooting-404-errors-for-github-pages-sites

### 11.1 Option a - simplest: copy the file into docs/ and publish from main /docs

```powershell
Copy-Item .\site\index.html .\docs\index.html -Force
pwsh -NoProfile -File .\scripts\publish\publish.ps1 -UserName <github-user> -UserEmail <your-email> -Description "The evidence-backed, judge-free failure probe kit for LLMs." -Execute
```

The second command commits and pushes the new `docs/index.html` through the
same idempotent publish path. Then, in the browser:

1. Open the repository's **Settings -> Pages**.
2. Under **Build and deployment -> Source**, choose **Deploy from a branch**.
3. Branch: `main`, folder: `/docs`, then **Save**.
4. Wait 1-2 minutes (the first deployment can take a few minutes), then open
   `https://<github-user>.github.io/llm-failbench/`.

Notes for this option:

- Pages serves `docs/index.html` and the static files that file links to. The
  other files in `docs/` are markdown documentation and are not part of the
  dashboard; the dashboard is fully self-contained, so it works without them.
- The copy must be regenerated whenever the site/report is regenerated
  (`python -m failbench report --results results/demo --out site` followed by
  copying `site/index.html` again and re-running the publish script).
  Otherwise Pages will show a stale dashboard.
- If you would rather commit manually, the equivalent is:
  "`git add docs/index.html` / `git commit -m "docs: publish dashboard"` /
  authenticated push" using the manual push in Section 7.1. The publish
  script always uses the commit message `release: failbench v0.1.0`, so use
  the manual form when the commit message must describe the change.

### 11.2 Option b - cleaner: GitHub Actions Pages workflow

Add this file as `.github/workflows/pages.yml` and set **Settings -> Pages ->
Build and deployment -> Source** to **GitHub Actions**. It deploys the `site`
folder as-is, so no copy step and no stale duplicate.

```yaml
name: pages

on:
  push:
    branches: [ main ]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Configure Pages
        uses: actions/configure-pages@v5
      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: site
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

The dashboard is published at `https://<github-user>.github.io/llm-failbench/`
after the workflow run finishes. The workflow pattern above follows the
documented publishing flow (checkout, upload the static artifact, deploy):
https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site

Add this file later, not during the build: `.github/workflows/` is owned by
the QA workstream (W5) while the project is being assembled, and its CI file
must stay untouched during that time. The repository owner can add
`pages.yml` after publishing, or ask the maintainer to integrate it.

### 11.3 Option c - skip Pages

Do not enable Pages. Share the repository URL and tell readers they can open
`site/index.html` locally, or view the same content through the README and
`docs/RESULTS.md`. The dashboard is self-contained and opens directly in a
browser from a checkout. This is a completely valid v0.1.0 outcome.

### 11.4 Optional release artifacts

If you want downloadable artifacts on the release page, build them:

```powershell
pwsh -NoProfile -File .\scripts\publish\make_archive.ps1
```

Artifacts land in `_scratch\dist\` (gitignored): `failbench-v0.1.0.zip`,
`failbench-v0.1.0.bundle`, and `SHA256SUMS.txt`. Attach them in the release
editor only if you intend to distribute them; the secret guard in
`make_archive.ps1` must have reported clean first. The bundle is skipped when
the repository has no commits yet, so build it after the first publish.

---

## 12. Step 10 - Post-publish checklist

- [ ] README renders correctly on the repository landing page (no broken
      relative links, images, or code fences; the mock-demo honesty note is
      visible)
- [ ] LICENSE is detected as MIT (repository sidebar shows the MIT label)
- [ ] CITATION.cff is present and the **Cite this repository** button appears
      in the sidebar (GitHub reads it from the default branch)
- [ ] Description set (Section 9.1)
- [ ] Topics set to the verified 15 (Section 9.2)
- [ ] Issues enabled (default) and the three issue forms open without errors
- [ ] Discussions enabled if desired (Section 9.3)
- [ ] Release v0.1.0 is published, notes render as markdown, and the tag points
      at the release commit
- [ ] CI is green on `main` (Actions tab) - a red workflow must be fixed or
      explained before announcing
- [ ] Site opens at `https://<github-user>.github.io/llm-failbench/` if Pages
      was enabled; otherwise the local-file and README paths are documented
- [ ] Repository URL added to README badges and CITATION metadata where
      appropriate (the build leaves the final URL to the owner)
- [ ] No secrets in the commit history. Run this only in this terminal (the
      token is set), and do not paste the output anywhere:

```powershell
& .\_scratch\Git\bin\git.exe log -p --all -S $env:GITHUB_TOKEN --oneline
```

`-S` searches the diff history for commits where the number of occurrences of
the string changed. The expected output is nothing at all: it means the token
string never appeared in any commit, in any branch, or in any tag. Any output
is an incident - stop, rotate the token (Section 14.13), and clean up history.
The same check against a non-secret marker such as `ghp_` is a useful
alternative when the token is no longer set.

- [ ] `& .\_scratch\Git\bin\git.exe remote -v` shows a plain HTTPS URL with no
      `user:token@` prefix and no token query string
- [ ] The working tree is clean (`git status -sb`): no stray files were left
      uncommitted by the publish
- [ ] Release artifacts distributed only if desired (Section 11.4), and
      `SHA256SUMS.txt` kept alongside them
- [ ] Announce honestly using the drafts in `launch/` only after the checks
      above pass: no fake accounts, no vote manipulation, no mass unsolicited
      messages, no invented metrics or endorsements, and no claims that any
      model was measured in this build

---

## 13. Updates, rebuilding, and version bumps

### 13.1 Routine update (same version)

1. Edit the repository files in the usual way and re-run the local checks:
   `python -m unittest discover -s tests -t . -v` and
   `python -m failbench validate --strict`.
2. Dry run the publish to see the plan.
3. Execute:

```powershell
pwsh -NoProfile -File .\scripts\publish\publish.ps1 -UserName <github-user> -UserEmail <your-email> -Description "The evidence-backed, judge-free failure probe kit for LLMs."
pwsh -NoProfile -File .\scripts\publish\publish.ps1 -UserName <github-user> -UserEmail <your-email> -Description "The evidence-backed, judge-free failure probe kit for LLMs." -Execute
```

The script is idempotent: it commits the changed files as
`release: failbench v0.1.0` and pushes. If the commit message must describe a
particular change, either edit the message in the script (it is a single
literal in `publish.ps1`) or commit manually with the manual push in
Section 7.1 and re-run the script only to push. Note that changing the script's
commit message is a code change that itself needs a commit; keep the message
in sync with the release version.

### 13.2 Version bump for a new release

1. Update the version in `pyproject.toml` and `CITATION.cff`, and add the new
   section at the top of `CHANGELOG.md` (keep older sections).
2. Re-run the offline tests and strict validation.
3. Commit and push through the publish script, then create an annotated tag
   for the new version, for example `v0.2.0`:

```powershell
& .\_scratch\Git\bin\git.exe -c user.name="<github-user>" -c user.email="<your-email>" tag -a v0.2.0 -m "FailBench v0.2.0"
& .\_scratch\Git\bin\git.exe -c credential.helper= -c "http.extraheader=AUTHORIZATION: basic $basic" push origin v0.2.0
```

`$basic` is the base64 credential value from Section 10.1; recompute it if this
is a new terminal:
`$basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('x-access-token:' + $env:GITHUB_TOKEN))`.

4. Create the release with the same REST pattern as Section 10.3, changing
   `tag_name`, `name`, and `body` to the new version. Reuse the release-notes
   structure and update the "What this release contains" and honest-status
   sections truthfully; do not copy old metrics forward.
5. Optionally adjust the publish script's commit message literal to the new
   version so future commits are labeled correctly.

### 13.3 Rebuild the release archive

```powershell
pwsh -NoProfile -File .\scripts\publish\make_archive.ps1 -Version 0.1.0
```

`-Version` defaults to `0.1.0` and must match `^[0-9]+\.[0-9]+\.[0-9]+$`.
Use `-SkipBundle` if only the source ZIP is needed, `-OutDir` to place the
artifacts elsewhere, and `-RepoRoot` to archive another checkout. The script
is idempotent and overwrites stale artifacts. Exit codes: 0 success, 1 build
failure, 2 secret-like content detected (nothing is written in that case).
Artifacts are written under `_scratch\dist` and are never committed.

### 13.4 Rebuild the site and report

After new demo results or evidence, regenerate the dashboard and report with
the CLI, then re-publish:

```powershell
python -m failbench report --results results/demo --out site
```

If Pages Option a is in use, re-copy `site/index.html` to `docs/index.html`
before re-running the publish script (Section 11.1).

---

## 14. Troubleshooting

Each entry lists the symptom, the likely cause, and the fix. Re-run the dry
run after any fix; the publish script is idempotent and safe to retry.

### 14.1 `401 Bad credentials`

Cause: the token is mistyped, expired, revoked, or has whitespace/newline
characters from the copy; or the token was set in another terminal and is
missing here.

Fix: re-run the masked prompt in this terminal (Section 5.1) and paste the token
without surrounding whitespace. Check expiry at
https://github.com/settings/tokens. Verify only the length (Section 5.3). For a
classic token, length 40 is expected; a classic token that has not been used
for a year is removed automatically, so expired is common.

### 14.2 `403 Forbidden` / `Resource not accessible by personal access token`

Causes, in order of likelihood: the token is missing a scope (classic `repo`
is required for repository creation, metadata, releases, and push; `workflow`
is required for workflow files); an organization policy restricts classic
tokens (not applicable to a personal account); the token belongs to a
different account than the `<github-user>` owner; a fine-grained token lacks
the repository permissions; or you hit a primary or secondary rate limit
(authenticated calls can still be rate-limited, and a secondary limit can
appear as a burst of `403` responses even when the token is valid).

Fix: read the response body for the API's `message` and `documentation_url`,
then regenerate/repair the token with the scopes in Section 4.1. Confirm you are
using the token for the same account that will own the repository. If a
fine-grained token is in play, switch to classic.

### 14.3 `422 Validation Failed` / repository name already exists

If the repository already exists under the same owner, the publish script
treats it as success and continues (idempotent path); a `422` with
`already_exists` there is expected on re-runs. If the name is taken by a
different owner, the name is unavailable for your account: pick another name
with `-RepoName <new-name>`. If the API complains about the name format,
remember that repository names may contain letters, digits, `-`, `_`, and `.`,
must not start with a dash, and cannot be just spaces; `llm-failbench` is
valid. A `422` can also mean the request body was invalid (for example an
empty name) - read `errors` in the response.

### 14.4 Push fails: `Authentication failed` or `could not read Username for 'https://github.com'`

Cause: the push had no credentials. The remote URL intentionally contains no
token, and a plain `git push` therefore asks a credential helper (or the
terminal) for a username/password. With `GIT_TERMINAL_PROMPT=0` it fails
instead of prompting. This is not a broken token.

Fix: use the publish script (it adds the per-process credential header), or
re-run the manual push in Section 7.1 or the tag push in Section 10.1. If a
credential manager keeps popping up, disable it for that command with
`-c credential.helper=` as shown. Never "fix" this by embedding the token in
the remote URL.

### 14.5 Push rejected: `refusing to allow a Personal Access Token to create or update workflow`

Cause: the token lacks the `workflow` scope, and the push includes
`.github/workflows/ci.yml` (or any other workflow file).

Fix: edit the classic token at https://github.com/settings/tokens and add the
`workflow` scope (or generate a new token with `repo` + `workflow`), set it
again in the terminal (Section 5.1), then re-run the publish. The workflow file
stays in the repository - this is purely a token permission problem. The
scope requirement follows from
https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens

### 14.6 `Updates were rejected because the remote contains work that you do not have locally`

Cause: the remote repository has commits your local `main` does not have -
typically because the repository was created through the web UI with a README,
license, or `.gitignore`, or someone pushed to it.

Fix, in order of preference:

1. If the remote content was accidental (a throwaway first attempt), delete
   the remote repository and re-run the publish script against a clean
   repository created with `auto_init = $false`.
2. Otherwise integrate: fetch and rebase or merge before pushing.

```powershell
& .\_scratch\Git\bin\git.exe fetch origin
& .\_scratch\Git\bin\git.exe -c user.name="<github-user>" -c user.email="<your-email>" rebase origin/main
$env:GIT_TERMINAL_PROMPT = '0'
$basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('x-access-token:' + $env:GITHUB_TOKEN))
& .\_scratch\Git\bin\git.exe -c credential.helper= -c "http.extraheader=AUTHORIZATION: basic $basic" push -u origin main
```

Do not use `--force` on a shared public repository. If the histories are
unrelated and the remote only contains an auto-generated README, the cleanest
path is deleting and recreating the empty repository, then pushing.

### 14.7 `fatal: not a git repository (or any of the parent directories): .git`

Cause: the command is running in the wrong directory, or `-RepoRoot` points
somewhere else.

Fix: `Set-Location '<repo-root>'` (replace it with the absolute path of your
clone) and re-run, or
pass `-RepoRoot` explicitly. The publish script normally initializes `.git`
itself, so this error usually means the script is being run from a different
shell directory than the repository it is targeting.

### 14.8 `git: command not found` / the script cannot find git

Cause: portable git was moved or the `_scratch` folder was cleaned; git is not
on `PATH`.

Fix: confirm `& .\_scratch\Git\bin\git.exe --version` works. If the portable
copy is gone, pass `-GitPath` with the path to `git.exe` **or** to the `bin`
directory that contains it (both are accepted by the publish script), or set
`$env:FAILBENCH_GIT` to the executable path for the session. The two scripts
resolve git in slightly different orders:

- `publish.ps1`: `-GitPath` first, then `$env:FAILBENCH_GIT`, then
  `<repo>\_scratch\Git\bin\git.exe`, then the portable git next to the script
  checkout, then `git` on `PATH`. It prints the resolved path in
  `[1/7] Environment` and tells you to set `FAILBENCH_GIT` if nothing is
  found.
- `make_archive.ps1`: `<repo>\_scratch\Git\bin\git.exe`, then the script
  checkout's `_scratch\Git\bin\git.exe`, then `$env:FAILBENCH_GIT`, then
  `git` on `PATH`.

### 14.9 PowerShell execution policy blocks the .ps1 files

Symptom: `... cannot be loaded because running scripts is disabled on this
system`.

Fix: prefer running through `pwsh -NoProfile -File .\scripts\publish\publish.ps1 ...`,
which is how this guide invokes it. If your machine policy still blocks the
file, allow scripts for the current process only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

This affects the current process only, not the machine or the user profile.
Do not lower the machine-wide policy for this task.

### 14.10 Warnings: `LF will be replaced by CRLF` / `CRLF will be replaced by LF`

Cause: Windows git converts line endings on checkout/commit according to
`core.autocrlf`; the repository does not pin line endings because it has no
`.gitattributes` yet. This is a warning, not an error; the push succeeds and
the published text files are fine.

Fix: none required. Integration item for the maintainers: add a
`.gitattributes` that normalizes text files (for example
`* text=auto eol=lf` plus explicit binary rules) so future contributors do
not see the warning. Do not create that file as part of publishing; it is a
repository-content change for the build owners.

### 14.11 GitHub rejects a file larger than 100 MB

Cause: GitHub's hard limit for a single file in a git push is 100 MB; pushes
containing larger blobs are rejected. You should not hit this in this
repository because `_scratch/` and raw `results/` are gitignored, but a
stray archive or dataset can slip in.

Fix: remove it from tracking without deleting the local file, for example
`& .\_scratch\Git\bin\git.exe rm --cached -- path\to\large-file`, ensure the
path is gitignored, commit, and push. If the large file is already in
history, removing it requires a history rewrite (see GitHub's guidance:
https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).
Prefer the clean path: fix `.gitignore`/the build before the first push.

### 14.12 GitHub Pages returns 404

Causes: Pages is not enabled; the source branch/folder does not match where
`index.html` actually is; the deployment is still queued; `index.html` is not
at the top level of the chosen folder; the file name's case is wrong; or the
repository was created private on a plan without Pages.

Fix: check **Settings -> Pages** for the current source and the last
deployment status; check **Actions** for the Pages deployment run; wait 1-2
minutes (first deploy can take longer); confirm the file is
`docs/index.html` (not `Docs/` and not `Index.html`) for Option a or that the
workflow uploads `site` for Option b. On a private repository on a free plan,
Pages is unavailable - switch visibility or skip Pages. The 404 checklist is
at
https://docs.github.com/en/pages/getting-started-with-github-pages/troubleshooting-404-errors-for-github-pages-sites

### 14.13 A token was leaked

Act immediately, in this order:

1. Revoke the token at https://github.com/settings/tokens (delete it). A
   revoked token cannot be used even if it is in some log or history.
2. Generate a replacement token with `repo` + `workflow` and set it in the
   terminal again (Section 5.1).
3. If the token was committed or pushed, remove it from history and force-push
   the cleaned history, then contact GitHub Support to purge cached views:
   https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
   Follow that guide's ordering: revoke first, rewrite second, coordinate any
   collaborators - and note the guide's warning that rewritten commits change
   hashes and open pull requests may break.
4. Audit what the token could reach (the scopes you granted) and check the
   repository's security log for unexpected activity.
5. Do not paste the leaked value into any issue, PR, or chat to "report" it.

---

## 15. Security notes

- Never paste the token into chat, issues, commit messages, scripts, source
  files, URLs, screenshots, or shared terminal logs. It is a password.
- The token is scope-limited: use `repo` + `workflow` only, never
  `admin:org`, `delete_repo`, or `gist`, and set an expiry of 30-90 days.
- The token is session-only and process-scoped. It lives in
  `$env:GITHUB_TOKEN` for this terminal; clear it with
  `Remove-Item Env:GITHUB_TOKEN` when finished. Never put it in a PowerShell
  profile, `.env` file, or any tracked file.
- The publish script passes the token to git as a per-process HTTP header and
  never stores it. The remote URL stays credential-free.
- If you revoke the token after publishing, nothing breaks: the repository
  remains public, and future pushes require a fresh token. Do that
  deliberately when the token is only needed for this release.
- 2FA stays enabled on the account, with recovery codes stored offline or in
  a password manager. A committed recovery code is as dangerous as a token.
- Use a credential manager only if you understand where it persists secrets.
  This workflow does not need one; if a helper exists on the machine, the
  one-shot push commands in this guide bypass it with
  `-c credential.helper=`. If you do let a helper store the token, know that
  it lives in the OS credential store, not in git.
- Audit for accidental persistence before announcing: run
  `& .\_scratch\Git\bin\git.exe config --local --list` and
  `& .\_scratch\Git\bin\git.exe config --global --list`, and confirm nothing
  contains `http.extraheader`, `credential.helper`, a token, or a password.
  Also confirm `Get-ChildItem Env: | Where-Object Name -like '*TOKEN*'`
  shows only the variables you expect.
- Prefer the masked prompt and never `echo` the token. If you suspect the
  terminal's scrollback, transcript, or shell history captured it, rotate the
  token first and investigate second.
- Treat `_scratch/` as private: it holds tools and archives, is gitignored,
  and must never be added to the repository.

---

## 16. Quick copy-paste sequence (Steps 2-9)

Run from the repository root in PowerShell 7. Replace the three placeholders
at the top before running. The release-notes text is defined once in Step 8
and is not repeated here; paste it from Section 10.2 when you reach the release.

```powershell
# Run in the repository root in PowerShell 7. Replace the three placeholders below.
$githubUser = '<github-user>'
$userEmail  = '<your-email>'
$repoName   = 'llm-failbench'

# Step 2/3: token (masked prompt; paste the classic PAT with repo + workflow scopes).
$env:GITHUB_TOKEN = Read-Host -MaskInput 'Paste GitHub PAT'
if ([string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)) { throw 'GITHUB_TOKEN is missing' }
'set, length ' + $env:GITHUB_TOKEN.Length

# Step 4: dry run (safe; no network writes).
pwsh -NoProfile -File .\scripts\publish\publish.ps1 -UserName $githubUser -UserEmail $userEmail -RepoName $repoName -Description "The evidence-backed, judge-free failure probe kit for LLMs."

# Step 5: execute.
pwsh -NoProfile -File .\scripts\publish\publish.ps1 -UserName $githubUser -UserEmail $userEmail -RepoName $repoName -Description "The evidence-backed, judge-free failure probe kit for LLMs." -Execute

# Step 6: verify locally and through the API (prints three fields only).
& .\_scratch\Git\bin\git.exe remote -v
& .\_scratch\Git\bin\git.exe log --oneline -1
$headers = @{
    'User-Agent'    = 'failbench-publish-check'
    'Authorization' = "Bearer $env:GITHUB_TOKEN"
}
$repo = Invoke-RestMethod -Uri "https://api.github.com/repos/$githubUser/$repoName" -Headers $headers
$repo.html_url
$repo.visibility
$repo.default_branch

# Step 7: description and topics.
$headers = @{
    'User-Agent'    = 'failbench-publish-metadata'
    'Authorization' = "Bearer $env:GITHUB_TOKEN"
    'Accept'        = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
}
$repoBody = @{ description = 'The evidence-backed, judge-free failure probe kit for LLMs. Deterministic probes, sourced evidence, no LLM judges.' } | ConvertTo-Json
Invoke-RestMethod -Method Patch -Uri "https://api.github.com/repos/$githubUser/$repoName" -Headers $headers -Body $repoBody -ContentType 'application/json' | Out-Null
$topics = @('llm','llm-evaluation','model-evaluation','evaluation','benchmark','benchmarking','testing','reproducibility','deterministic','hallucination','ai-safety','prompt-engineering','openai','llmops','github-pages')
$topicsBody = @{ names = $topics } | ConvertTo-Json
Invoke-RestMethod -Method Put -Uri "https://api.github.com/repos/$githubUser/$repoName/topics" -Headers $headers -Body $topicsBody -ContentType 'application/json' | Out-Null
'topics set: ' + $topics.Count

# Step 8: annotated tag and authenticated tag push.
& .\_scratch\Git\bin\git.exe -c user.name="$githubUser" -c user.email="$userEmail" tag -a v0.1.0 -m "FailBench v0.1.0"
$env:GIT_TERMINAL_PROMPT = '0'
$basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('x-access-token:' + $env:GITHUB_TOKEN))
& .\_scratch\Git\bin\git.exe -c credential.helper= -c "http.extraheader=AUTHORIZATION: basic $basic" push origin v0.1.0

# Step 8 release: paste the here-string from Section 10.2 here, then POST the payload.
# $releaseNotes = @' ... '@
# $payload = @{ tag_name='v0.1.0'; name='FailBench v0.1.0'; draft=$false; prerelease=$false; body=$releaseNotes } | ConvertTo-Json -Depth 3
# $null = $payload | ConvertFrom-Json
# Invoke-RestMethod -Method Post -Uri "https://api.github.com/repos/$githubUser/$repoName/releases" -Headers $headers -Body $payload -ContentType 'application/json'

# Step 9 (optional): Pages from main /docs.
# Copy-Item .\site\index.html .\docs\index.html -Force
# pwsh -NoProfile -File .\scripts\publish\publish.ps1 -UserName $githubUser -UserEmail $userEmail -RepoName $repoName -Description "The evidence-backed, judge-free failure probe kit for LLMs." -Execute
# Then: Settings -> Pages -> Deploy from a branch -> main / /docs -> Save.

# Cleanup: remove the token from this session when done.
Remove-Item Env:GITHUB_TOKEN
```

The commented release and Pages blocks are the only parts that are not
runnable as-is; uncomment them together with the Section 10.2 here-string.

---

## 17. Files and scripts referenced

| File | Role |
|---|---|
| `scripts\publish\publish.ps1` | Safe publish driver: validates inputs, dry run by default, creates the repository through the REST API, commits and pushes `main` with a per-process credential header. Parameters include `-UserName`, `-RepoName` (default `llm-failbench`), `-UserEmail`, `-Description`, `-Private`, `-Execute`, `-GitPath`, `-RepoRoot`. |
| `scripts\publish\make_archive.ps1` | Builds `_scratch\dist\failbench-v0.1.0.zip`, `failbench-v0.1.0.bundle`, and `SHA256SUMS.txt`; includes a secret guard that exits 2 on findings. |
| `CODE_OF_CONDUCT.md` | Community behavior expectations, linked from CONTRIBUTING and the README. |
| `SECURITY.md` | Responsible-disclosure policy for the tool; read it before reporting a security issue publicly. |
| `.github\ISSUE_TEMPLATE\bug_report.yml` | Bug report issue form. |
| `.github\ISSUE_TEMPLATE\evidence_submission.yml` | Evidence submission form (public source URL + exact quote required). |
| `.github\ISSUE_TEMPLATE\probe_request.yml` | Probe request form. |
| `.github\PULL_REQUEST_TEMPLATE.md` | Contribution checklist tied to the build contract. |
| `LICENSE` | MIT license for the code. |
| `CITATION.cff` | Citation metadata; enables the GitHub "Cite this repository" button once the repository URL is final. |
| `docs\CONTRACT.md` | Authoritative schema, ownership, and quality rules. |
| `docs\DISTRIBUTION.md` and `launch\` | Truthful launch and distribution drafts; no automated posting. |

### Where to get help

- Environment and script problems: re-read the matching entry in Section 14,
  then run the dry run with the failing inputs and read the `[ERROR]` line.
- Repository-content problems: open an issue at
  `https://github.com/<github-user>/llm-failbench/issues` using the matching
  template.
- Security issues in FailBench itself: follow `SECURITY.md` instead of opening
  a public issue.

### Integration items for maintainers

- Add a `.gitattributes` for deterministic line endings (Section 14.10).
- Decide whether GitHub Pages is enabled, and if so regenerate
  `docs/index.html` from `site/index.html` on every report rebuild
  (Section 11.1) or add the Pages workflow after the build
  (Section 11.2, owned by W5 during the build).
- Fill in the final repository URL in `README.md`, `pyproject.toml`
  `[project.urls]`, and `CITATION.cff` (`repository-code`) once it is known.
- Keep the publish script's commit-message literal in sync with the current
  version.

---

## Appendix A - Verified reference links

All links below were checked on 2026-11-24 with an HTTP HEAD/GET request; the
`docs.github.com` pages returned HTTP 200 after redirects, and the status
column reflects that. Topic pages were checked with direct HTTPS requests
(HTTP 200 and a populated topic listing); they are listed in Section 9.2.

| URL | Status |
|---|---|
| https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens | 200 |
| https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28#create-a-repository-for-the-authenticated-user | 200 |
| https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28#update-a-repository | 200 |
| https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28#replace-all-repository-topics-for-a-repository | 200 |
| https://docs.github.com/en/rest/releases/releases?apiVersion=2022-11-28#create-a-release | 200 |
| https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api?apiVersion=2022-11-28 | 200 |
| https://docs.github.com/en/rest/authentication/endpoints-available-for-fine-grained-personal-access-tokens | 200 |
| https://docs.github.com/en/authentication/securing-your-account-with-two-factor-authentication-2fa/configuring-two-factor-authentication | 200 |
| https://docs.github.com/en/authentication/securing-your-account-with-two-factor-authentication-2fa/about-mandatory-two-factor-authentication | 200 |
| https://docs.github.com/en/account-and-profile/how-tos/account-management/creating-an-account-on-github | 200 |
| https://docs.github.com/en/account-and-profile/reference/email-addresses-reference | 200 |
| https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address | 200 |
| https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics | 200 |
| https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-citation-files | 200 |
| https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository | 200 |
| https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview | 200 |
| https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/enabling-or-disabling-github-discussions-for-a-repository | 200 |
| https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository | 200 |
| https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site | 200 |
| https://docs.github.com/en/pages/getting-started-with-github-pages/troubleshooting-404-errors-for-github-pages-sites | 200 |
| https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository | 200 |
| https://docs.github.com/en/github-cli/github-cli/about-github-cli | 200 |

The sign-up page itself (https://github.com/signup) is the page linked from
the GitHub account-creation documentation above; automated fetches of it may
be blocked by bot protection, which does not affect a normal browser.
