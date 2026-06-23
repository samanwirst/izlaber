import type { AnalyticsSummary, SponsoredCampaign } from "./types";

export async function getAnalyticsSummary(days = 30): Promise<AnalyticsSummary> {
  return (await internalFetch(`/v1/analytics/summary/?days=${days}`)) as AnalyticsSummary;
}

export async function getSponsoredCampaigns(): Promise<SponsoredCampaign[]> {
  try {
    return (await internalFetch("/v1/sponsored-campaigns/")) as SponsoredCampaign[];
  } catch (error) {
    if (error instanceof ServerAPIError && error.status === 404) {
      return [];
    }
    throw error;
  }
}

export async function createSponsoredCampaign(payload: Record<string, unknown>) {
  return internalFetch("/v1/sponsored-campaigns/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateSponsoredCampaign(
  campaignId: number,
  payload: Record<string, unknown>,
) {
  return internalFetch(`/v1/sponsored-campaigns/${campaignId}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

async function internalFetch(path: string, init: RequestInit = {}) {
  const baseUrl = process.env.SERVER_API_BASE_URL ?? "http://127.0.0.1:8000/api";
  const apiKey = process.env.ANALYTICS_API_KEY || process.env.BOT_API_KEY;

  if (!apiKey) {
    throw new Error("ANALYTICS_API_KEY or BOT_API_KEY is required for analytics site.");
  }

  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("X-Internal-API-Key", apiKey);
  if (init.body) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.text();
    throw new ServerAPIError(
      response.status,
      `Server API returned HTTP ${response.status}: ${body.slice(0, 220)}`,
    );
  }

  return response.json();
}

class ServerAPIError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}
