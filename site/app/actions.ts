"use server";

import { revalidatePath } from "next/cache";
import { createSponsoredCampaign, updateSponsoredCampaign } from "../lib/api";
import { requireDashboardAuth } from "../lib/auth";

export async function createSponsoredCampaignAction(formData: FormData) {
  await requireDashboardAuth();
  const payload = {
    name: field(formData, "name"),
    advertiser_name: field(formData, "advertiser_name"),
    product_lookup: field(formData, "product_lookup"),
    keywords: listField(formData, "keywords"),
    language_codes: listField(formData, "language_codes"),
    status: field(formData, "status") || "draft",
    priority: intField(formData, "priority") ?? 100,
    starts_at: nullableField(formData, "starts_at"),
    ends_at: nullableField(formData, "ends_at"),
    daily_impression_limit: intField(formData, "daily_impression_limit"),
    total_impression_limit: intField(formData, "total_impression_limit"),
    notes: field(formData, "notes"),
  };

  await createSponsoredCampaign(payload);
  revalidatePath("/");
}

export async function updateSponsoredCampaignStatusAction(formData: FormData) {
  await requireDashboardAuth();
  const campaignId = intField(formData, "campaign_id");
  const status = field(formData, "status");
  if (!campaignId || !status) {
    throw new Error("campaign_id and status are required.");
  }

  await updateSponsoredCampaign(campaignId, { status });
  revalidatePath("/");
}

function field(formData: FormData, name: string) {
  return String(formData.get(name) ?? "").trim();
}

function nullableField(formData: FormData, name: string) {
  const value = field(formData, name);
  return value || null;
}

function listField(formData: FormData, name: string) {
  return field(formData, name)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function intField(formData: FormData, name: string) {
  const value = field(formData, name);
  if (!value) {
    return null;
  }
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : null;
}
