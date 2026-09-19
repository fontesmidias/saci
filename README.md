# Saci

> **A router for free-tier LLMs. When one runs out, it hops to the next.**
> *Sempre dá um jeito.* — [Versão em português](README.pt-BR.md)

[![CI](https://github.com/fontesmidias/saci/actions/workflows/ci.yml/badge.svg)](https://github.com/fontesmidias/saci/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Status: beta](https://img.shields.io/badge/status-beta-orange.svg)](CHANGELOG.md)

Saci is for people who **can't pay for LLM APIs** — students, small teams, anyone
between subscriptions. It turns the free tiers of Groq, Google AI Studio, Mistral,
NVIDIA NIM, OpenRouter and others into **one local OpenAI-compatible endpoint**
that never runs dry:

- **Fallback cascade, per model.** Quota exhausted (429), model removed (404/410),
  provider down (5xx), prompt too large (413) — Saci tries the next model. It tracks
  quota *per model*, because Groq counts tokens per model, not per account.
- **Quota you can see.** Live bars, the hour each quota resets *in your timezone*,
  and an honest label on every number: `official` (from the provider's headers) or
  `estimated` (our local count).
- **A catalog that maintains itself.** Every hour Saci fetches each provider's model
  list, filters out non-chat models, and probes each *new* one once. Only what
  answered `200` with your key enters the cascade. Add a key, and the provider joins
  on its own.
- **Works with the tools you already use.** Verified with **Cline** (VS Code) and
  **Aider** (terminal). Anything that speaks the OpenAI API works.

Named after the [Saci](https://en.wikipedia.org/wiki/Saci_(Brazilian_folklore)),
the one-legged trickster of Brazilian folklore who always finds a way.

---

## Quick start (Windows)

```powershell
git clone https://github.com/fontesmidias/saci
cd saci
py -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
copy .env.example .env        # paste at least one key (see table below)
saci-on                       # server on http://127.0.0.1:8000 — stays up via PM2
saci-panel                    # dashboard in your browser
```

`saci-on` needs [PM2](https://pm2.keymetrics.io/) (`npm i -g pm2`). Without it, run
`.venv\Scripts\python.exe server.py` in a terminal you keep open.
Linux/macOS: `python -m saci.server` — the `.cmd` shortcuts are Windows-only for now.

### Free keys (no credit card)

| Provider | Get a key | Why it's in the cascade |
|---|---|---|
| Groq | https://console.groq.com/keys | Fastest by far (~0.5 s); 1,000 req/day |
| Google AI Studio | https://aistudio.google.com/apikey | Biggest context, 1,500 req/day |
| Mistral | https://console.mistral.ai/ | `codestral` is excellent for code |
| NVIDIA NIM | https://build.nvidia.com/ | Large open models (slow, but free) |
| OpenRouter | https://openrouter.ai/keys | Dozens of `:free` models — the only one that publishes pricing |
| SambaNova | https://cloud.sambanova.ai/ | Llama/DeepSeek, 30 RPM |
| Hugging Face | https://huggingface.co/settings/tokens | Serverless open models |
| LLM7.io | *no key needed* | Keyless last resort |

Hyperbolic is supported too but spends **prepaid credit** — Saci flags it everywhere.

---

## Use it

### From Cline, Aider, or any OpenAI client

| Setting | Value |
|---|---|
| Base URL | `http://127.0.0.1:8000/v1` |
| API key | anything (the server is local and doesn't check it) |
| Model | `saci-code` · `saci-plan` · `saci-agent` · `saci-fast` · `saci-long` · `saci-pt` |

Each "model" is a **task profile** — an ordered cascade tuned for that job:

| Profile | For | Starts with |
|---|---|---|
| `saci-code` | writing / refactoring code | Groq `gpt-oss-120b`, Mistral `codestral` |
| `saci-plan` | architecture, trade-offs | Groq `gpt-oss-120b`, Gemini |
| `saci-agent` | coding agents (huge prompts) | Mistral, Gemini — providers that accept 413-sized requests |
| `saci-fast` | quick questions | Groq `gpt-oss-20b` |
| `saci-long` | long documents | Gemini (1M context) |
| `saci-pt` | Brazilian Portuguese, formal text | Gemini, Groq |

Prompts over ~24k characters are promoted to `saci-agent` automatically, whatever
model you asked for — so Cline just works.

Aider: copy [`~/.aider.conf.yml`](CONTRIBUTING.md) with
`openai-api-base: http://127.0.0.1:8000/v1` and `model: openai/saci-code`.

### From the terminal

```powershell
saci "explain database indexes in one sentence"
saci -p code "python function that validates a Brazilian CPF"
type app.py | saci -p code "add tests:"
saci --usage        # quota per provider and model, reset times
saci --catalog      # every discovered model and its verdict
saci --refresh      # discover + probe now
```

### The dashboard and the status bar

`saci-panel` opens `http://127.0.0.1:8000/dashboard`:

- quota bar per provider, **"resets at 21:00"** with a live countdown
- every discovered model with its verdict — `ok`, `paid`, `gone`, `rate-limited` —
  and a **use** button to pin one
- profile switch, "check catalog now", server RAM footprint

The `vscode-statusbar/` folder is a tiny local VS Code extension: it shows
`⚡ groq 1% · 21:00` in the status bar; clicking it opens a picker to switch profile
or pin any verified model. Install by copying the folder to
`%USERPROFILE%\.vscode\extensions\local.saci-status-0.1.0` and reloading the window.

---

## How "free" is decided

This is the part every "free LLM list" gets wrong, so here it is plainly:

- **Only OpenRouter publishes pricing** in its model list.
- Groq, Google, Mistral, NVIDIA and the rest publish *names*. Some of those names
  return `404`, `410`, `402` or `403` the moment you call them.
- So Saci **probes**: one 3-word request per new model, once. `200` → usable.
  `402/403` → paid, never retried for 30 days. `404/410` → gone. `429` → retried
  in an hour. `ok` models are re-checked every 14 days to catch silent removals.

The result is a list you didn't write and don't maintain — and that's the point.

## Quota tracking, honestly

| Provider | Source | What we know |
|---|---|---|
| Groq, Mistral | **official** — response headers | remaining requests & tokens, reset time |
| OpenRouter | official — `/v1/key` | accumulated usage |
| Google, NVIDIA, others | **estimated** — local count | calls and tokens today vs. known daily limit |

Every number in the UI carries its label. A model past 95 % of its quota moves to
the *end* of the cascade rather than being dropped: if the quota reset since we
last looked, it still gets its turn.

## Status (verified 2026-09-19)

| Provider | Works | Latency | Notes |
|---|---|---|---|
| Groq | ✅ | 0.3–2 s | 6 chat models verified; fastest |
| Google AI Studio | ✅ | 1–25 s | `gemini-2.5-*` are **gone** (404) despite what lists say |
| Mistral | ✅ | 0.5–2 s | 12 free, 2 paid (`labs-*`), free tier is 1 req/s |
| NVIDIA NIM | ⚠️ | 15–70 s | 46 of 62 listed chat models return 404/410/503 |
| OpenRouter | ⚠️ | varies | 25 free of 419; `:free` models are contended |
| LLM7.io | ⚠️ | ~3 s | keyless; unstable output, last resort only |
| Hyperbolic | 💳 | — | prepaid credit, flagged |
| Cerebras | ❌ | — | 402 on a free account |

## Roadmap

- **0.2 — desktop app:** system-tray icon, native window, settings screen for keys,
  data in `%APPDATA%`, Windows installer. Replaces PM2 and the `.cmd` files.
- Cross-platform launcher (Linux/macOS get first-class shortcuts).
- Per-model rate limiter for agents that fire parallel requests.

See [CHANGELOG.md](CHANGELOG.md).

## Contributing

The most useful PR is a provider that works or a limit that changed — see
[CONTRIBUTING.md](CONTRIBUTING.md). One rule: paste the probe output. Catalogs lie.

Security notes in [SECURITY.md](SECURITY.md): keys stay on your machine, the server
binds to `127.0.0.1` and has no auth — don't expose it.

## License

[MIT](LICENSE) © Bruno Fontes
