# site/AGENTS.md

Rules for analytics site work:

- This is a Next.js App Router application.
- Fetch server data from Server Components or server utilities only; never expose internal API keys to the browser.
- Keep dashboard auth server-side in `site/lib/auth.ts`; Server Actions that mutate analytics/admin data must call `requireDashboardAuth()`.
- Dashboard UI should stay dense, calm, and useful for analysts. Avoid marketing-page sections.
- Keep charts tied to `AnalyticsSummary` from `site/lib/types.ts`.

Useful checks:

```bash
cd site
npm run typecheck
npm run build
```
