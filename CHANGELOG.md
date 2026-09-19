# Changelog

All notable changes to Saci are documented here.
*Em português: [CHANGELOG.pt-BR.md](CHANGELOG.pt-BR.md).*
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: [SemVer](https://semver.org/).

## [Unreleased]

Planned for 0.2.0 — the desktop app:
- System-tray icon with live quota (`groq 1% · 21:00`) and a native window for the dashboard
- Settings screen to paste API keys and reorder providers (no more editing `.env`)
- Data under `%APPDATA%\Saci` (keys, history, catalog) so updates never touch them
- Log file, start with Windows, "check for updates"
- Windows installer; the app replaces PM2

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

[Unreleased]: https://github.com/fontesmidias/saci/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/fontesmidias/saci/releases/tag/v0.1.0
