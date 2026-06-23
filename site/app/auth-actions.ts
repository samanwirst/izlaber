"use server";

import { redirect } from "next/navigation";
import {
  clearLoginState,
  completeLoginChallenge,
  startLoginChallenge,
} from "../lib/auth";

export async function requestLoginCodeAction(formData: FormData) {
  let ok = false;
  try {
    ok = await startLoginChallenge(
      field(formData, "username"),
      field(formData, "password"),
    );
  } catch {
    redirect("/?login=telegram-failed");
  }
  if (!ok) {
    redirect("/?login=invalid");
  }
  redirect("/?login=code-sent");
}

export async function verifyLoginCodeAction(formData: FormData) {
  const ok = await completeLoginChallenge(field(formData, "code"));
  if (!ok) {
    redirect("/?login=bad-code");
  }
  redirect("/");
}

export async function resetLoginAction() {
  await clearLoginState();
  redirect("/");
}

export async function logoutAction() {
  await clearLoginState();
  redirect("/?login=logged-out");
}

function field(formData: FormData, name: string) {
  return String(formData.get(name) ?? "").trim();
}
