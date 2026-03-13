# OSS Mirror Utilities

This folder contains scripts to export a sanitized, open-source mirror from your private workspace.

## What it does

- Copies only allowlisted files/folders (`allowlist.txt` or `profiles/*.allowlist`)
- Removes common local-only artifacts (`__pycache__`, `.DS_Store`, `output/`, `archive/`, `.state/`)
- Redacts personal paths and placeholders in copied text files
- Runs a sensitive-pattern scan before syncing
- Applies optional profile overlays for mirror-only release files
- Syncs to a target mirror directory (`_oss_mirror` by default)

## Scripts

- `sync_oss_mirror.sh`: build and sync mirror
- `push_oss_mirror.sh`: commit + push mirror repo
- `install_mirror_hook.sh`: install mirror pre-commit privacy guard
- `verify_oss_mirror.sh`: sync + verify mirror freshness and emit a concise report
- `check_env_template.sh`: ensure release `.env.example` covers all env keys used by source code
- `check_requirements_template.sh`: ensure release `requirements*.txt` stays aligned with source imports and report root-level unrelated dependencies

## Usage

Preview mirror diff:

```bash
bash codes/oss_mirror/sync_oss_mirror.sh --preview
```

Preview with profile:

```bash
bash codes/oss_mirror/sync_oss_mirror.sh --preview --profile seed_to_literature
```

Sync mirror:

```bash
bash codes/oss_mirror/sync_oss_mirror.sh --sync
```

Install pre-commit guard in mirror repo:

```bash
bash codes/oss_mirror/install_mirror_hook.sh
```

Push mirror (after mirror repo is initialized):

```bash
bash codes/oss_mirror/push_oss_mirror.sh --remote origin --branch main
```

## First-time setup for mirror repo

```bash
cd _oss_mirror
git init
git remote add origin <your-public-repo-url>
```

## Safety note

The exporter uses an allowlist. Keep `allowlist.txt` minimal and explicit.
Every run also writes a scan report to `codes/oss_mirror/reports/`.

## Reusable profile workflow

1. Create `codes/oss_mirror/profiles/<project>.allowlist`
2. (Optional) Create `codes/oss_mirror/overlays/<project>/` for mirror-only files like `README.md`, `.env.example`, `.gitignore`, `LICENSE`
   - For generated README, use `README.overlay.template.md` + `README.sections` (+ optional `README.source`)
3. Run `--preview --profile <project>`
4. Run `--sync --profile <project>`
5. Push from `_oss_mirror`


Verify (sync + post-sync drift check):

```bash
bash codes/oss_mirror/verify_oss_mirror.sh --profile seed_to_literature
```


Env coverage check:

```bash
make oss-env-check OSS_PROFILE=seed_to_literature
```

Requirements coverage check:

```bash
make oss-req-check OSS_PROFILE=seed_to_literature
```
