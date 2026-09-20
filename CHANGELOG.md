# Changelog

All notable changes to Saci are documented here.
*Em português: [CHANGELOG.pt-BR.md](CHANGELOG.pt-BR.md).*
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: [SemVer](https://semver.org/).

## [Unreleased]

## [0.2.0] — 2026-09-19

The desktop app. Beta: the installer and packaged `.exe` are new and have
only been tested by the author on one machine — expect rough edges.

### Added
- **Windows installer** (`Saci.iss`, Inno Setup): installs to
  `%LOCALAPPDATA%\Programs\Saci`, no administrator rights required. Detects
  a missing WebView2 Runtime before installing and offers the official
  download. Uninstall asks before deleting `%APPDATA%\Saci`, and always
  removes the autostart registry entry so it never points at a deleted `.exe`.
- **System-tray app** (`saci-app` / `Saci.exe`): a cap-shaped icon that
  changes color with quota usage (green/amber/red), a native window for the
  dashboard, and a menu — Open dashboard, Settings, Profile (submenu),
  Check catalog now, Open logs folder, Start with Windows, Exit. Closing the
  window only hides it; a second launch detects the running instance (via
  `/health`, not just the port) and opens the browser to it instead of
  starting twice.
- **Settings screen** (`/settings`): paste, test (without saving) and save
  API keys per provider, with the value always masked back
  (`gsk_••••f7dR`) — the raw key is never sent back to the browser. Also
  edits the fallback order, timezone and default profile, previously
  `.env`-only.
- **Data moved to `%APPDATA%\Saci`** when running installed: `.env`,
  `usage.db`, `prefs.json`, `logs/saci.log` (rotating, 2 MB × 3 files). Data
  from an existing development install is copied — never moved — the first
  time the packaged app runs.
- **Versioned database migrations** (`saci/migrations.py`): schema changes
  are now additive or `RENAME`-based, never `DROP TABLE` — a real bug fixed
  in the process (`quota`'s old single-`provider` key was being dropped on
  every startup with a schema change, discarding live quota state).
- **Start with Windows**, toggled from the tray menu; writes to `HKCU`, no
  admin needed.

### Fixed
Two bugs that only manifested inside the packaged `.exe`, invisible in
every test that ran from source (the packaging step itself is what surfaced
them):
- The app crashed silently on startup: `Analysis(["saci/app.py"])` made
  PyInstaller treat it as a top-level script, breaking every relative
  import (`from . import paths`) inside it. Fixed with `saci_launcher.py`,
  a thin entry point outside the `saci` package that imports it normally.
- The server intermittently never accepted connections (anywhere from 3s to
  over 100s to respond, unpredictably) because `uvicorn.run()`'s automatic
  event-loop detection could hang inside the frozen executable. Fixed by
  passing `loop="asyncio"` explicitly.

Also fixed: the model catalog crashed against LLM7 (`Error binding
parameter: type 'dict' is not supported`) because that provider reports
context length as a nested object instead of a plain number.

Also fixed: if the server thread died from an unhandled exception, it died
silently — the packaged `.exe` has no console (`--windowed`), so the
traceback went nowhere and the tray just showed "unavailable" with no clue
why. The server thread now catches and logs the exception to `saci.log`.

### Verified
Installer runs silently and unattended (`/VERYSILENT`) without admin
rights; the installed executable creates `%APPDATA%\Saci` correctly, serves
the dashboard and settings pages, and answers real chat requests. Three
consecutive cold starts of the packaged `.exe` after the asyncio fix: all
three ready in 3 seconds.

## [0.1.0] — 2026-09-19

First public release. Beta: works daily for the author; expect rough edges.

### Added
- **Fallback cascade** across free-tier providers. On 429 (quota), 5xx, timeout,
  404/410 (model removed) or 413 (request too large) the next model is tried —
  by *model*, not by provider, because e.g. Groq counts tokens per model.
- **Task profiles** exposed as OpenAI model names: `saci-code`, `saci-plan`,
  `saci-agent`, `saci-fast`, `saci-long`, `saci-pt`. Prompts above ~24k chars are
  promoted to `agent` automatically (Groq rejects them with 413).
- **OpenAI-compatible local server** (`http://127.0.0.1:8000/v1`) — verified with
  Cline (VS Code) and Aider (terminal). Streaming, multimodal `content` blocks and
  the `developer` role are handled.
- **Automatic model catalog**: at start-up and hourly, every provider's `/models` is
  fetched, filtered to chat models, and each *new* model is probed once
  (200 ok · 402/403 paid · 404/410 gone · 429 rate-limited). New providers join the
  cascade on their own after the first probe. Only OpenRouter publishes pricing;
  everywhere else "free" means "answered 200 with your key".
- **Quota tracking** from official response headers where they exist (Groq,
  Mistral) and from local counting elsewhere — the UI always says which one.
  Per-provider daily reset shown as clock time in your timezone
  (`LLM_ROUTER_TZ`, default São Paulo).
- **Dashboard** (`/dashboard`): quota bars, live countdown to reset, per-model
  verdicts, profile switch, pin a model, "check catalog now", RAM footprint.
- **VS Code status-bar extension** (local install): `⚡ groq 1% · 21:00`; click
  opens a quick-pick to switch profile or pin any verified model.
- **CLI**: `saci "question"`, `--usage`, `--catalog`, `--refresh`, `--status`,
  `--profiles`; pipe files in.
- **Windows shortcuts** (`saci-on`, `saci-off`, `saci-panel`, `saci-usage`,
  `saci-logs`, `saci-status`) on top of PM2, resilient to daemon loss.
- Aider configuration example (`~/.aider.conf.yml`) pointing at the router.

### Verified providers (2026-09-19)
Groq · Google AI Studio · Mistral · NVIDIA NIM · OpenRouter (`:free`) ·
LLM7.io (keyless) · SambaNova · Hugging Face · Hyperbolic (prepaid credit, flagged).
Cerebras returns 402 on a free account; SiliconFlow sign-up was not approved.

[Unreleased]: https://github.com/fontesmidias/saci/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/fontesmidias/saci/releases/tag/v0.2.0
[0.1.0]: https://github.com/fontesmidias/saci/releases/tag/v0.1.0
