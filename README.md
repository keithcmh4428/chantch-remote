# CHANTCH Remote client: branded RustDesk builds (Windows .exe/.msi, macOS .dmg)

Plan: `docs/rustdesk-plan.md`, Phase 4. Server: `deploy/rustdesk/README.md`.
This folder is the **overlay**: the only things we add to RustDesk. It is kept here and copied into its own public
GitHub repo, `keithcmh4428/chantch-remote` (public because of AGPL-3.0, below; public repos also get free Windows and
macOS build minutes). We never edit RustDesk's code in place, and never keep a long-lived fork.

| File | What it does |
|---|---|
| `brand.env` | names, bundle id, server, server key |
| `assets/logo.png` | the logo (not in this repo yet: `assets/README.md`) |
| `apply.py` | 16 anchored source edits + every icon regenerated from the logo |
| `make_workflow.py` | trims upstream's own build workflow to Windows + macOS, points the packaging at the app name |
| `workflows/release.yml` | the daily job (goes to `.github/workflows/release.yml` in the client repo) |
| `test-local.sh` | dry run against any upstream tag on a Linux/WSL machine, no GitHub needed |

## How a release happens

```
03:00 MYT  release.yml (client repo, default branch)
           latest github.com/rustdesk/rustdesk release, e.g. 1.5.0   (never nightly)
           already a 1.5.0-chantch.N release here?  -> stop
           clone 1.5.0 untouched (+ hbb_common submodule)
           apply.py + make_workflow.py                         any upstream drift -> run fails, nothing published
           one commit, pushed as branch build/1.5.0-chantch.1  (hbb_common vendored in, CHANTCH-NOTICE.md)
           pre-release 1.5.0-chantch.1 created on that commit
     push  chantch-build.yml (on that branch) -> upstream flutter-build.yml jobs:
           generate-bridge, build-RustDeskTempTopMostWindow, build-for-windows-flutter (x64 + arm64),
           build-for-macOS (x86_64 + aarch64) -> assets on the pre-release
           rename-assets: rustdesk-1.5.0-x86_64.exe -> CHANTCHRemote-1.5.0-x86_64.exe (.msi, .dmg), SHA256SUMS.txt
by hand    a technician tests the pre-release, then marks it "Latest" (GitHub -> Releases -> Edit)
```

**Promotion is manual.** Customers download from `https://github.com/keithcmh4428/chantch-remote/releases/latest`,
which only shows releases a person marked Latest.

**A failed run** (upstream moved a line, or the build broke) sends GitHub's failure e-mail to the repo owner. Nothing is
published and the last good release stays Latest. Then:
- **Drift:** fix the one edit named in the log (in `apply.py` or `make_workflow.py`), here and in the client repo.
- **Build breakage:** check whether upstream's own build of that tag is green.
- Run *Actions → CHANTCH Remote release → Run workflow* with **rebuild** ticked. That build gets the next number, e.g.
  `1.5.0-chantch.2`.

The daily job never builds the same upstream tag twice on its own.

Branded clients **do not update themselves.** RustDesk's updater would install stock RustDesk from
github.com/rustdesk, so `apply.py` switches it off for this client. New versions reach machines by re-running the
installer: customers from the Latest link, staff PCs by RMM/script.

## What the overlay changes (`apply.py`, checked against RustDesk 1.5.0)

- **Server and key:**
  - `libs/hbb_common/src/config.rs`: `RENDEZVOUS_SERVERS = ["remote.chantch.com"]`, and `RS_PUB_KEY` = the server's
    key.
  - Without a configured API server, the client falls back to `admin.rustdesk.com`, but upstream skips the
    heartbeat/sysinfo upload for `*.rustdesk.com`, so the client sends nothing to RustDesk's servers.
- **Name:**
  - `APP_NAME = CHANTCHRemote` and `ORG = com.chantch` (same file).
  - Upstream detects a custom client by `APP_NAME != "RustDesk"`. That flag switches off RustDesk's own update banner
    and some stock-only UI.
- **Why `CHANTCHRemote`, not `CHANTCH Remote`:** RustDesk's macOS code expects
  `/Applications/<APP_NAME>.app/Contents/MacOS/<APP_NAME>`. It builds launchd labels `<ORG>.<APP_NAME>_service` and
  shell commands from the name without quoting. "CHANTCH Remote" is still shown where a space is safe:
  - Windows file properties (`Cargo.toml` winres, `Runner.rc`: ProductName, FileDescription, CompanyName);
  - the app's own texts, where upstream replaces "RustDesk" with the app name.
- **macOS:**
  - `AppInfo.xcconfig`: `PRODUCT_NAME = CHANTCHRemote` (so `CHANTCHRemote.app`), bundle id `com.chantch.remote`,
    copyright line naming RustDesk/AGPL.
  - `CHANTCHRemote.app` replaces `RustDesk.app` in `project.pbxproj`, `build.py` (copies the service binary into the
    bundle) and `res/osx-dist.sh`.
- **Updater:** `src/updater.rs` `check_update()` returns at once for a custom client, even if someone ticks *Auto
  update*. Upstream already skips it on macOS.
- **Icons:** regenerated from `assets/logo.png` at the size of each upstream file:
  - `res/*.png`;
  - `res/icon.ico` and `app_icon.ico`, with the full 16–256 px set (upstream's `app_icon.ico` is 48 px only);
  - `tray-icon.ico`;
  - `AppIcon.icns`;
  - the macOS tray: a black silhouette of the logo (template image), or `assets/tray-mac.png` if given;
  - `flutter/assets/icon.svg` and `res/logo.svg`: an SVG wrapping the PNG.

`make_workflow.py` changes:
- **MSI:** renames the dist's `rustdesk.exe` to `CHANTCHRemote.exe` before `preprocess.py --app-name CHANTCHRemote`.
  The installed exe is `<APP_NAME>.exe` in upstream's own install code too.
- **Dropped steps:** the two MSI-template steps, which serve RustDesk Server Pro's generator.
- **macOS packaging:** `RustDesk.app` becomes `CHANTCHRemote.app` in the macOS job.
- **Other workflows:** every other upstream workflow is deleted from the build branch (CI, nightly, Android, Linux,
  ...).

## Setting it up (once)

1. **Logo:** copy the logo to `assets/logo.png` (`assets/README.md`).
2. **Key:** after the server is installed, put its key into `brand.env`:
   `RS_PUB_KEY=<contents of /opt/chantch/rustdesk/data/id_ed25519.pub>`. It is not a secret.
3. **Repo:** create the public repo `keithcmh4428/chantch-remote` and copy into it:
   - `apply.py`, `make_workflow.py`, `brand.env`, `test-local.sh`, `assets/`, this README;
   - `workflows/release.yml` → `.github/workflows/release.yml`.

   Also add RustDesk's `LICENSE` (AGPL-3.0).
4. **Push token:**
   - Create a fine-grained token: *GitHub → Settings → Developer settings → Fine-grained tokens*.
   - Repository access: only `chantch-remote`. Permissions: **Contents: Read and write**, **Workflows: Read and
     write**. Give it an expiry and a reminder.
   - Save it as the repo secret **`BUILD_PUSH_TOKEN`**. It is needed because GitHub's built-in token may not push
     workflow files, and its pushes would not start the build.
5. **Actions settings** (repo → *Settings → Actions → General*): allow actions, and give *Workflow permissions:
   Read and write* (the build creates releases).
6. **First run:** *Actions → CHANTCH Remote release → Run workflow*. Then test the pre-release (§ below) and mark it
   Latest.

### Signing

- **macOS (needed before customers):** an unsigned dmg is blocked by Gatekeeper. Upstream's macOS job already signs
  and notarises when these **repo secrets** exist (same names as RustDesk's):
  - `MACOS_P12_BASE64` and `MACOS_P12_PASSWORD`: the *Developer ID Application* certificate as a base64 .p12 and its
    password;
  - `MACOS_CODESIGN_IDENTITY`: e.g. `Developer ID Application: CHANTCH SDN BHD (TEAMID)`;
  - `MACOS_NOTARIZE_JSON`: base64 of the App Store Connect API key JSON made by
    `rcodesign encode-app-store-connect-api-key`.

  Needs the Apple Developer Program (organisation).
- **Windows (strongly recommended):** not wired yet. Upstream signs through RustDesk's private signing service
  (`SIGN_BASE_URL`), which we cannot use, so the exe/msi come out **unsigned** and SmartScreen warns. When a
  certificate is chosen (cloud HSM: DigiCert/SSL.com/Sectigo, or Azure Artifact Signing if eligible), add a signing
  step to `make_workflow.py`. It should replace "Sign rustdesk files" and "Sign rustdesk self-extracted file" with
  the provider's action.

### Testing a pre-release (before marking it Latest)

- **Install:** on a Windows PC and a Mac (Apple silicon and Intel if both are in use).
  - Windows: the exe installs to `C:\Program Files\CHANTCHRemote`, and the service *CHANTCHRemote* runs.
  - Mac: `/Applications/CHANTCHRemote.app` is granted Screen Recording + Accessibility, and the service starts after a
    reboot.
- **Settings:** *Settings → Network* shows `remote.chantch.com` and our key without anyone typing them.
- **Connections:** connect in and out from outside the office, then once with *Always use relay* switched on.
- **Features:** file transfer, and recording to the configured folder.
- **Uninstall:** leaves no service behind.

## Licence (AGPL-3.0)

The client is RustDesk, AGPL-3.0. Customers receive our modified binaries, so they must be able to get the exact
source:
- every release is tagged on its `build/<release>` branch in the public repo;
- that branch holds `CHANTCH-NOTICE.md`, naming the upstream commit and the overlay commit;
- keep RustDesk's `LICENSE` in the repo and the "based on RustDesk" line in the About box (copyright line above).

Do not call the product RustDesk or use RustDesk's logo.

## Tested (2026-10-20, agent sandbox, RustDesk 1.5.0)

- `apply.py` on a fresh 1.5.0 checkout:
  - all 16 edits applied (diff reviewed);
  - the icons are valid: ICO size sets, an ICNS with 16–1024 px, a single-colour macOS tray image.
- `make_workflow.py`:
  - kept 4 of 16 jobs and 3 workflow files, and removed 8 workflows;
  - the result passes `actionlint` with no new findings. The only remaining notes are upstream's own, on its
    TopMostWindow reusable workflow; upstream's two errors were in jobs we drop.
- **Fail-safe:** a moved anchor (simulated) stops the run with the file and edit named, and nothing is written. A
  space in `APP_NAME`, an empty `RS_PUB_KEY` and a bad release tag are refused.
- `release.yml`:
  - passes `actionlint` with shellcheck;
  - its commit step's own script (extracted from the YAML) built the orphan commit from a shallow clone and pushed it
    to a local bare repo: hbb_common vendored with our edits, no `.gitmodules`, notice written.
- **Not tested** (only GitHub's Windows/macOS runners can do it):
  - the actual Windows and macOS builds, signing, the asset renaming against a real release;
  - the branded app running: installed name, service and launchd labels, Mac permissions, connecting to
    remote.chantch.com.

  The first real run and the checklist above are that test.
