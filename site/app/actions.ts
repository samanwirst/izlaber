"use server";

import { revalidatePath } from "next/cache";
import {
  createAnalyticsEvent,
  createSponsoredCampaign,
  getActiveUserConsents,
  updateSponsoredCampaign,
} from "../lib/api";
import { requireDashboardAuth } from "../lib/auth";

export type BroadcastActionState = {
  status: "idle" | "success" | "error";
  message: string;
  recipientCount?: number;
  sentCount?: number;
  failedCount?: number;
};

const TELEGRAM_BATCH_SIZE = 20;
const TELEGRAM_BATCH_DELAY_MS = 1100;
const TELEGRAM_MESSAGE_LIMIT = 4096;

const INITIAL_BROADCAST_STATE: BroadcastActionState = {
  status: "idle",
  message: "",
};

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

export async function sendBroadcastAction(
  _previousState: BroadcastActionState = INITIAL_BROADCAST_STATE,
  formData: FormData,
): Promise<BroadcastActionState> {
  await requireDashboardAuth();

  const text = field(formData, "message");
  const messageType = field(formData, "message_type") === "service" ? "service" : "sponsored";
  const confirmed = formData.get("confirm_broadcast") === "on";
  if (!confirmed) {
    return { status: "error", message: "Подтвердите массовую отправку." };
  }
  if (!text) {
    return { status: "error", message: "Введите текст рассылки." };
  }

  const message = broadcastMessageText(text, messageType);
  if (message.length > TELEGRAM_MESSAGE_LIMIT) {
    return {
      status: "error",
      message: `Сообщение слишком длинное: ${message.length}/${TELEGRAM_MESSAGE_LIMIT}.`,
    };
  }

  const token = process.env.TELEGRAM_BOT_TOKEN || process.env.BOT_TOKEN;
  if (!token) {
    return {
      status: "error",
      message: "TELEGRAM_BOT_TOKEN или BOT_TOKEN не настроен для сайта.",
    };
  }

  const recipients = await getActiveUserConsents();
  const chatIds = uniqueTelegramIds(
    recipients
      .filter((recipient) => recipient.has_active_consent)
      .map((recipient) => recipient.telegram_user_id),
  );
  if (chatIds.length === 0) {
    return { status: "error", message: "Нет активных пользователей с согласием." };
  }

  const stats = await sendTelegramBroadcast({ token, chatIds, text: message });

  try {
    await createAnalyticsEvent({
      event_type: "admin_broadcast_sent",
      source: "server",
      input_type: messageType,
      result_count: stats.sent,
      query: text.slice(0, 500),
      metadata: {
        recipient_count: chatIds.length,
        sent_count: stats.sent,
        failed_count: stats.failed,
      },
    });
  } catch (error) {
    console.error("Cannot record broadcast analytics event:", error);
  }

  revalidatePath("/");
  return {
    status: stats.failed > 0 ? "error" : "success",
    message:
      stats.failed > 0
        ? `Отправлено ${stats.sent}, ошибок ${stats.failed}.`
        : `Отправлено ${stats.sent} пользователям.`,
    recipientCount: chatIds.length,
    sentCount: stats.sent,
    failedCount: stats.failed,
  };
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

function broadcastMessageText(text: string, messageType: "service" | "sponsored") {
  if (messageType === "service") {
    return text;
  }
  return `Рекламное предложение\n\n${text}`;
}

function uniqueTelegramIds(values: number[]) {
  const ids: number[] = [];
  const seen = new Set<number>();
  for (const value of values) {
    if (!Number.isSafeInteger(value) || seen.has(value)) {
      continue;
    }
    ids.push(value);
    seen.add(value);
  }
  return ids;
}

async function sendTelegramBroadcast({
  token,
  chatIds,
  text,
}: {
  token: string;
  chatIds: number[];
  text: string;
}) {
  let sent = 0;
  let failed = 0;

  for (let index = 0; index < chatIds.length; index += TELEGRAM_BATCH_SIZE) {
    const batch = chatIds.slice(index, index + TELEGRAM_BATCH_SIZE);
    const results = await Promise.allSettled(
      batch.map((chatId) => sendTelegramMessage({ token, chatId, text })),
    );
    for (const result of results) {
      if (result.status === "fulfilled" && result.value) {
        sent += 1;
      } else {
        failed += 1;
      }
    }
    if (index + TELEGRAM_BATCH_SIZE < chatIds.length) {
      await sleep(TELEGRAM_BATCH_DELAY_MS);
    }
  }

  return { sent, failed };
}

async function sendTelegramMessage({
  token,
  chatId,
  text,
}: {
  token: string;
  chatId: number;
  text: string;
}) {
  const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text,
      disable_web_page_preview: false,
    }),
  });
  if (!response.ok) {
    const body = await response.text();
    console.error(`Telegram broadcast failed: ${response.status} ${body}`);
    return false;
  }
  return true;
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
