# Security

Flightdeck observes your session and stores short summaries of tool calls in session state (see "What it can reach" in the README). It makes no network requests, runs no processes, and reads or writes no files.

If you find a way it could leak data, for example a credential format that `redact()` in `hooks/core.ts` misses, please report it privately through GitHub's **Security → Report a vulnerability** on this repository rather than in a public issue.
