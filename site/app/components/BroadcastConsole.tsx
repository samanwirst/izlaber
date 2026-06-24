"use client";

import { useActionState } from "react";
import { sendBroadcastAction, type BroadcastActionState } from "../actions";
import { formatNumber } from "../../lib/format";

type BroadcastConsoleProps = {
  activeConsentCount: number;
};

const initialState: BroadcastActionState = {
  status: "idle",
  message: "",
};

export function BroadcastConsole({ activeConsentCount }: BroadcastConsoleProps) {
  const [state, formAction, pending] = useActionState(sendBroadcastAction, initialState);

  return (
    <section className="dashboard-shell campaign-shell broadcast-shell">
      <div className="topbar compact-topbar">
        <div>
          <p className="eyebrow">Audience messaging</p>
          <h1>Broadcast console</h1>
          <p className="muted">
            Send a Telegram message to users with active data and ads consent.
          </p>
        </div>
        <div className="status-pill">
          <span />
          {formatNumber(activeConsentCount)} reachable
        </div>
      </div>

      <section className="grid-12">
        <div className="panel span-5">
          <PanelHeader
            caption="Sponsored messages are labeled before delivery"
            title="New broadcast"
          />
          <form action={formAction} className="campaign-form">
            <label>
              Message type
              <select name="message_type" defaultValue="sponsored">
                <option value="sponsored">Sponsored message</option>
                <option value="service">Service message</option>
              </select>
            </label>
            <label>
              Message text
              <textarea
                maxLength={3900}
                name="message"
                placeholder="Напишите текст рассылки"
                required
              />
            </label>
            <label className="checkbox-label">
              <input name="confirm_broadcast" type="checkbox" required />
              Send to all active consent users
            </label>
            <button className="primary-button" disabled={pending} type="submit">
              {pending ? "Sending..." : "Send broadcast"}
            </button>
          </form>
        </div>

        <div className="panel span-7">
          <PanelHeader title="Delivery status" caption="Last submission result" />
          <div className="broadcast-status">
            {state.status === "idle" ? (
              <p className="empty-state">No broadcast sent in this session.</p>
            ) : (
              <div className={`broadcast-result broadcast-${state.status}`}>
                <strong>{state.message}</strong>
                <div className="broadcast-metrics">
                  <Metric label="Target" value={state.recipientCount} />
                  <Metric label="Sent" value={state.sentCount} />
                  <Metric label="Failed" value={state.failedCount} />
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
    </section>
  );
}

function PanelHeader({ title, caption }: { title: string; caption: string }) {
  return (
    <div className="panel-header">
      <div>
        <h2>{title}</h2>
        <p>{caption}</p>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value?: number }) {
  return (
    <span>
      {label} <b>{formatNumber(value ?? 0)}</b>
    </span>
  );
}
