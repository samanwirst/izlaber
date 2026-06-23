import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import {
  createHmac,
  randomBytes,
  randomInt,
  timingSafeEqual,
} from "node:crypto";

const SESSION_COOKIE = "izlaber_site_session";
const CHALLENGE_COOKIE = "izlaber_site_challenge";
const CODE_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
const DEFAULT_SESSION_TTL_SECONDS = 12 * 60 * 60;
const DEFAULT_CHALLENGE_TTL_SECONDS = 10 * 60;
const MAX_CHALLENGE_ATTEMPTS = 5;

type SignedSession = {
  username: string;
  expiresAt: number;
};

type SignedChallenge = {
  username: string;
  codeHash: string;
  nonce: string;
  attempts: number;
  expiresAt: number;
};

export type LoginState = {
  authenticated: boolean;
  hasChallenge: boolean;
  adminsConfigured: boolean;
};

export async function getLoginState(): Promise<LoginState> {
  return {
    authenticated: await isDashboardAuthenticated(),
    hasChallenge: Boolean(await readChallenge()),
    adminsConfigured: adminTelegramIds().length > 0,
  };
}

export async function isDashboardAuthenticated(): Promise<boolean> {
  const cookieStore = await cookies();
  const session = verifySignedValue<SignedSession>(cookieStore.get(SESSION_COOKIE)?.value);
  if (!session || session.expiresAt <= Date.now()) {
    return false;
  }
  return session.username === adminUsername();
}

export async function requireDashboardAuth(): Promise<void> {
  if (!(await isDashboardAuthenticated())) {
    redirect("/?login=session-required");
  }
}

export async function startLoginChallenge(username: string, password: string): Promise<boolean> {
  const cookieStore = await cookies();
  if (!safeEqual(username, adminUsername()) || !safeEqual(password, adminPassword())) {
    cookieStore.delete(CHALLENGE_COOKIE);
    return false;
  }

  const adminIds = adminTelegramIds();
  if (adminIds.length === 0) {
    cookieStore.delete(CHALLENGE_COOKIE);
    return false;
  }

  const code = generateCode();
  const nonce = randomBytes(16).toString("hex");
  const challenge: SignedChallenge = {
    username,
    codeHash: codeHash(code, nonce),
    nonce,
    attempts: 0,
    expiresAt: Date.now() + challengeTtlSeconds() * 1000,
  };

  await sendTelegramCode(adminIds, code);
  cookieStore.set(CHALLENGE_COOKIE, signValue(challenge), cookieOptions(challengeTtlSeconds()));
  return true;
}

export async function completeLoginChallenge(code: string): Promise<boolean> {
  const cookieStore = await cookies();
  const challenge = await readChallenge();
  if (!challenge) {
    cookieStore.delete(CHALLENGE_COOKIE);
    return false;
  }

  if (challenge.attempts >= MAX_CHALLENGE_ATTEMPTS) {
    cookieStore.delete(CHALLENGE_COOKIE);
    return false;
  }

  const valid = safeEqual(codeHash(code.trim(), challenge.nonce), challenge.codeHash);
  if (!valid) {
    cookieStore.set(
      CHALLENGE_COOKIE,
      signValue({ ...challenge, attempts: challenge.attempts + 1 }),
      cookieOptions(Math.max(1, Math.ceil((challenge.expiresAt - Date.now()) / 1000))),
    );
    return false;
  }

  const session: SignedSession = {
    username: challenge.username,
    expiresAt: Date.now() + sessionTtlSeconds() * 1000,
  };
  cookieStore.delete(CHALLENGE_COOKIE);
  cookieStore.set(SESSION_COOKIE, signValue(session), cookieOptions(sessionTtlSeconds()));
  return true;
}

export async function clearLoginState(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(CHALLENGE_COOKIE);
  cookieStore.delete(SESSION_COOKIE);
}

async function readChallenge(): Promise<SignedChallenge | null> {
  const cookieStore = await cookies();
  const challenge = verifySignedValue<SignedChallenge>(cookieStore.get(CHALLENGE_COOKIE)?.value);
  if (!challenge || challenge.expiresAt <= Date.now() || challenge.username !== adminUsername()) {
    return null;
  }
  return challenge;
}

function generateCode(): string {
  let code = "";
  for (let index = 0; index < 8; index += 1) {
    code += CODE_ALPHABET[randomInt(CODE_ALPHABET.length)];
  }
  return code;
}

async function sendTelegramCode(adminIds: string[], code: string): Promise<void> {
  const token = process.env.TELEGRAM_BOT_TOKEN || process.env.BOT_TOKEN;
  if (!token) {
    throw new Error("TELEGRAM_BOT_TOKEN is required to send analytics login codes.");
  }

  const text = [
    "Izlaber analytics login code:",
    `<code>${code}</code>`,
    "",
    "If you did not request it, ignore this message.",
  ].join("\n");

  await Promise.all(
    adminIds.map(async (chatId) => {
      const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          text,
          parse_mode: "HTML",
          disable_web_page_preview: true,
        }),
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`Telegram rejected analytics login code for admin ${chatId}.`);
      }
    }),
  );
}

function adminTelegramIds(): string[] {
  const raw = process.env.SITE_ADMIN_TELEGRAM_IDS || process.env.TELEGRAM_ADMIN_IDS || "";
  const trimmed = raw.trim();
  if (!trimmed) {
    return [];
  }
  if (trimmed.startsWith("[")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed)) {
        return parsed.map((item) => String(item).trim()).filter(isTelegramId);
      }
    } catch {
      return [];
    }
  }
  return trimmed.split(/[\s,;]+/).map((item) => item.trim()).filter(isTelegramId);
}

function isTelegramId(value: string): boolean {
  return /^[0-9]{3,20}$/.test(value);
}

function signValue(value: object): string {
  const payload = Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${payload}.${signature(payload)}`;
}

function verifySignedValue<T>(value: string | undefined): T | null {
  if (!value) {
    return null;
  }
  const [payload, providedSignature] = value.split(".", 2);
  if (!payload || !providedSignature || !safeEqual(signature(payload), providedSignature)) {
    return null;
  }
  try {
    return JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as T;
  } catch {
    return null;
  }
}

function signature(payload: string): string {
  return createHmac("sha256", authSecret()).update(payload).digest("base64url");
}

function codeHash(code: string, nonce: string): string {
  return createHmac("sha256", authSecret()).update(`${nonce}:${code}`).digest("base64url");
}

function safeEqual(left: string, right: string): boolean {
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right);
  if (leftBuffer.length !== rightBuffer.length) {
    return false;
  }
  return timingSafeEqual(leftBuffer, rightBuffer);
}

function cookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    maxAge,
    path: "/",
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
  };
}

function authSecret(): string {
  return (
    process.env.SITE_AUTH_SECRET ||
    process.env.NEXTAUTH_SECRET ||
    process.env.DJANGO_SECRET_KEY ||
    process.env.BOT_API_KEY ||
    "unsafe-local-dev-site-auth-secret"
  );
}

function adminUsername(): string {
  return process.env.SITE_ADMIN_USERNAME || "admin";
}

function adminPassword(): string {
  return process.env.SITE_ADMIN_PASSWORD || "admin";
}

function sessionTtlSeconds(): number {
  return positiveInt(process.env.SITE_AUTH_SESSION_TTL_SECONDS, DEFAULT_SESSION_TTL_SECONDS);
}

function challengeTtlSeconds(): number {
  return positiveInt(process.env.SITE_AUTH_CODE_TTL_SECONDS, DEFAULT_CHALLENGE_TTL_SECONDS);
}

function positiveInt(value: string | undefined, fallback: number): number {
  const parsed = Number.parseInt(value || "", 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}
