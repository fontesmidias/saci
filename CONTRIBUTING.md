# Contributing to Saci

Thanks for stopping by. Saci exists for people who can't pay for LLM APIs, so
the most valuable contributions are the unglamorous ones: a provider that works,
a limit that changed, a model that died. *Em português: [CONTRIBUTING.pt-BR.md](CONTRIBUTING.pt-BR.md).*

## The one rule

**Nothing enters the config without having answered a real request.**
Catalogs lie: models listed in `/models` return 404, 410 or 402 all the time.
If you add or change a provider or model, paste the output of `saci --catalog`
(or the probe result) in the PR. That's basically the whole review.

## Run it locally

```powershell
git clone https://github.com/fontesmidias/saci
cd saci
py -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env      # add at least one key
saci-on                     # server + hourly catalog (Windows, via PM2)
saci --usage                # or: .venv\Scripts\python.exe -m saci.cli --usage
```

On Linux/macOS run `python -m saci.server` directly; the `.cmd` shortcuts are
Windows-only for now (a cross-platform launcher is welcome).

## Add a provider

1. `saci/providers.py` — add a `Provider(...)`. Leave `models=[]`: the catalog
   discovers and probes them. Set `cost="credits"` if it spends prepaid balance.
2. `saci/usage.py` — add it to `KNOWN_LIMITS` with what you *know* (RPM/RPD,
   reset timezone, `period`). Unknown is fine; say `source="local"`.
3. `saci/catalog.py` — only if its `/models` needs special filtering
   (`_is_chat`) or publishes pricing (`_free_by_catalog`).
4. `.env.example` — the key name and where to get it.
5. Run `saci --refresh` and paste the result in the PR.

## Report a quota or limit change

Open an issue with the provider, the old limit, the new one and where you saw it
(headers, dashboard, docs). Limits change silently; this is how the table stays
honest.

## Changing the database schema

`usage.db` holds real user history — quota usage and the discovered model
catalog. **Never `DROP TABLE` or `ALTER` a table directly in `usage.py` or
`catalog.py`.** Every schema change is a new numbered migration in
`saci/migrations.py`, added to the end of `MIGRATIONS`. It must be additive
(`CREATE TABLE`, `ALTER TABLE ADD COLUMN`) or, when it must change a primary
key, rename the old table instead of dropping it (see `_m002_*` for the
pattern). A migration that would lose data needs the user's explicit sign-off
first — that's not a decision to make alone in a PR.

Test a migration against a database that already has rows, not just an empty
one: create one with the *old* schema, insert a few realistic rows, run
`saci.usage.init()`, and confirm the rows are still there.

## Code style

`ruff check saci` must pass. Match the surrounding code: small modules, comments
that explain *why*, Portuguese or English in comments — either is fine. Keep the
code simple enough for a 27B model to edit — that's a design goal, not a joke.

The project's unbreakable rules are in [CLAUDE.md](CLAUDE.md) and are enforced by
`python scripts/check_rules.py`. Run it before opening a PR.

## Pull requests

- One topic per PR.
- If behaviour changed, add a line to `CHANGELOG.md` **and** `CHANGELOG.pt-BR.md`,
  under *Unreleased* / *Não lançado*.
- Don't commit `.env`, `usage.db`, `prefs.json` or logs (they're ignored;
  double-check anyway).
- Documentation is always bilingual and complete in both languages: if you touch
  `README.md`, touch `README.pt-BR.md` in the same commit.
