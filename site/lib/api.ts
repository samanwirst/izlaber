import type { AnalyticsSummary } from "./types";

export async function getAnalyticsSummary(days = 30): Promise<AnalyticsSummary> {
  const baseUrl = process.env.SERVER_API_BASE_URL ?? "http://127.0.0.1:8000/api";
  const apiKey = process.env.ANALYTICS_API_KEY || process.env.BOT_API_KEY;

  if (!apiKey) {
    throw new Error("ANALYTICS_API_KEY or BOT_API_KEY is required for analytics site.");
  }

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/v1/analytics/summary/?days=${days}`, {
    headers: {
      Accept: "application/json",
      "X-Internal-API-Key": apiKey,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Analytics API returned HTTP ${response.status}: ${body.slice(0, 220)}`);
  }

  return (await response.json()) as AnalyticsSummary;
}
