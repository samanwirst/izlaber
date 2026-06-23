import {
  createSponsoredCampaignAction,
  updateSponsoredCampaignStatusAction,
} from "../actions";
import type { SponsoredCampaign, SponsoredCampaignStatus } from "../../lib/types";
import { formatDateTime, formatNumber, formatPercent } from "../../lib/format";

type SponsoredCampaignConsoleProps = {
  campaigns: SponsoredCampaign[];
};

const STATUS_LABELS: Record<SponsoredCampaignStatus, string> = {
  draft: "Draft",
  active: "Active",
  paused: "Paused",
  finished: "Finished",
};

export function SponsoredCampaignConsole({ campaigns }: SponsoredCampaignConsoleProps) {
  const activeCount = campaigns.filter((campaign) => campaign.status === "active").length;
  const impressions = campaigns.reduce((sum, campaign) => sum + campaign.impressions, 0);
  const clicks = campaigns.reduce((sum, campaign) => sum + campaign.clicks, 0);

  return (
    <section className="dashboard-shell campaign-shell">
      <div className="topbar compact-topbar">
        <div>
          <p className="eyebrow">Sponsored tools</p>
          <h1>Ad campaign control</h1>
          <p className="muted">
            Launch clearly labeled sponsored product cards and monitor their delivery.
          </p>
        </div>
        <div className="status-pill">
          <span />
          {activeCount} active
        </div>
      </div>

      <section className="kpi-grid">
        <MetricCard label="Campaigns" value={formatNumber(campaigns.length)} note="all statuses" />
        <MetricCard label="Active" value={formatNumber(activeCount)} note="currently eligible" />
        <MetricCard label="Sponsored views" value={formatNumber(impressions)} note="bot impressions" />
        <MetricCard label="Sponsored CTR" value={formatPercent(rate(clicks, impressions))} note="clicks / views" />
      </section>

      <section className="grid-12">
        <div className="panel span-4">
          <PanelHeader
            caption="Use internal product ID, source product ID, or a product URL"
            title="Create campaign"
          />
          <form action={createSponsoredCampaignAction} className="campaign-form">
            <label>
              Campaign name
              <input name="name" placeholder="Summer search boost" required />
            </label>
            <label>
              Advertiser
              <input name="advertiser_name" placeholder="Partner or seller name" required />
            </label>
            <label>
              Product lookup
              <input name="product_lookup" placeholder="Product ID, source ID, or URL" required />
            </label>
            <label>
              Keywords
              <textarea
                name="keywords"
                placeholder="iphone case, phone cover, chexol"
                required
              />
            </label>
            <label>
              Languages
              <input name="language_codes" placeholder="uz, ru, en or empty for all" />
            </label>
            <div className="form-grid">
              <label>
                Status
                <select name="status" defaultValue="active">
                  <option value="active">Active</option>
                  <option value="draft">Draft</option>
                  <option value="paused">Paused</option>
                </select>
              </label>
              <label>
                Priority
                <input defaultValue="100" min="1" name="priority" type="number" />
              </label>
            </div>
            <div className="form-grid">
              <label>
                Starts
                <input name="starts_at" type="datetime-local" />
              </label>
              <label>
                Ends
                <input name="ends_at" type="datetime-local" />
              </label>
            </div>
            <div className="form-grid">
              <label>
                Daily cap
                <input min="0" name="daily_impression_limit" placeholder="optional" type="number" />
              </label>
              <label>
                Total cap
                <input min="0" name="total_impression_limit" placeholder="optional" type="number" />
              </label>
            </div>
            <label>
              Notes
              <textarea name="notes" placeholder="Contract, period, placement comments" />
            </label>
            <button className="primary-button" type="submit">
              Launch campaign
            </button>
          </form>
        </div>

        <div className="panel span-8">
          <PanelHeader
            caption="Campaigns are always shown with the sponsored label in the bot"
            title="Campaigns"
          />
          <div className="campaign-list">
            {campaigns.map((campaign) => (
              <article className="campaign-row" key={campaign.id}>
                <div className="product-image">
                  {campaign.product.cover_image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img alt="" src={campaign.product.cover_image_url} />
                  ) : (
                    <span />
                  )}
                </div>
                <div className="campaign-main">
                  <div className="campaign-title-line">
                    <strong>{campaign.name}</strong>
                    <span className={`status-badge status-${campaign.status}`}>
                      {STATUS_LABELS[campaign.status]}
                    </span>
                  </div>
                  <small>{campaign.advertiser_name}</small>
                  <a href={campaign.product.canonical_url} rel="noreferrer" target="_blank">
                    {campaign.product.title}
                  </a>
                  <p>{campaign.keywords.join(", ")}</p>
                  <small>
                    Updated {formatDateTime(campaign.updated_at)}
                    {campaign.ends_at ? ` · ends ${formatDateTime(campaign.ends_at)}` : ""}
                  </small>
                </div>
                <div className="campaign-metrics">
                  <span>
                    Views <b>{formatNumber(campaign.impressions)}</b>
                  </span>
                  <span>
                    Clicks <b>{formatNumber(campaign.clicks)}</b>
                  </span>
                  <span>
                    CTR <b>{formatPercent(campaign.ctr)}</b>
                  </span>
                  <span>
                    Left{" "}
                    <b>
                      {campaign.remaining_total_impressions === null
                        ? "no cap"
                        : formatNumber(campaign.remaining_total_impressions)}
                    </b>
                  </span>
                </div>
                <div className="campaign-actions">
                  <StatusButton campaignId={campaign.id} status="active" />
                  <StatusButton campaignId={campaign.id} status="paused" />
                  <StatusButton campaignId={campaign.id} status="finished" />
                </div>
              </article>
            ))}
            {campaigns.length === 0 ? <p className="empty-state">No campaigns yet.</p> : null}
          </div>
        </div>
      </section>
    </section>
  );
}

function StatusButton({
  campaignId,
  status,
}: {
  campaignId: number;
  status: SponsoredCampaignStatus;
}) {
  return (
    <form action={updateSponsoredCampaignStatusAction}>
      <input name="campaign_id" type="hidden" value={campaignId} />
      <input name="status" type="hidden" value={status} />
      <button type="submit">{STATUS_LABELS[status]}</button>
    </form>
  );
}

function MetricCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
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

function rate(numerator: number, denominator: number) {
  if (denominator <= 0) {
    return 0;
  }
  return (numerator / denominator) * 100;
}
