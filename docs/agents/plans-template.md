# Plans Template

Use this for substantial code changes. Keep plans short and update statuses as work progresses.

## Plan

```md
## Goal

One sentence describing the requested outcome.

## Current Context

- Relevant service boundary:
- Files likely involved:
- Data/API/migration impact:
- Risks:

## Steps

1. Inspect current implementation and tests.
2. Implement the smallest change in the owning layer.
3. Update tests/docs/env examples if needed.
4. Run scoped verification.
5. Summarize behavior, checks, and remaining risks.

## Done Means

- Correct service boundary is preserved.
- Tests cover changed behavior or a concrete reason is given.
- Migrations/index rebuilds/env docs are handled if relevant.
- `git status --short` is reviewed.
```

## When To Use A Plan

- Cross-service bot/server/parser changes.
- Database model or migration work.
- Parser crawl behavior changes.
- AI/photo/voice behavior changes with cost or latency risk.
- Any change that could affect existing product data.

## When Not To Use A Plan

- Tiny docs-only edits.
- Single obvious test fixes.
- Small copy changes with clear files and no behavior risk.

