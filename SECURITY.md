# Security

## What Saci does with your API keys

- Keys live in **your** `.env` (and, from 0.2, in `%APPDATA%\Saci`). They are
  read at request time and sent **only** to the provider they belong to.
- Keys are never logged. Error messages are scrubbed before being stored or
  printed (`router.py::_scrub`).
- The server binds to `127.0.0.1` only and has **no authentication**. Do not
  expose port 8000 to a network without putting an authenticated reverse
  proxy in front. Anyone who can reach it can spend your quota.
- The catalog probe sends a fixed 3-word prompt to each new model, once.
  Nothing from your conversations is sent anywhere except to the provider
  answering that conversation.
- The dashboard, the VS Code extension and the CLI talk to the local server
  only. No telemetry, no phone-home, no update check in 0.1.

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's
private reporting: *Security → Report a vulnerability* on the repository.
You'll get an answer within a week; fixes for confirmed issues are released
as soon as they're ready and credited in the changelog unless you prefer not.

## Supported versions

Only the latest release receives fixes.
