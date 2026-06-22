"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AnalyticsSummary, NamedValue } from "../../lib/types";
import { formatDate, formatDateTime, formatNumber, formatPercent } from "../../lib/format";

const CHART_COLORS = ["#1f7a54", "#1f5c99", "#c57a1b", "#6c4aa3", "#9d3d55", "#56616f"];

type DashboardProps = {
  summary: AnalyticsSummary;
};

export function AnalyticsDashboard({ summary }: DashboardProps) {
  const conversion = [
    { name: "Searches", value: summary.kpis.searches },
    { name: "Impressions", value: summary.kpis.impressions },
    { name: "Clicks", value: summary.kpis.clicks },
  ];

  return (
    <main className="dashboard-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Izlaber Intelligence</p>
          <h1>Product search analytics</h1>
          <p className="muted">
            {summary.period.days} дней, обновлено {formatDateTime(summary.generated_at)}
          </p>
        </div>
        <div className="status-pill">
          <span />
          Live data
        </div>
      </header>

      <section className="kpi-grid">
        <MetricCard label="Users" value={formatNumber(summary.kpis.users)} note="unique Telegram IDs" />
        <MetricCard label="Searches" value={formatNumber(summary.kpis.searches)} note="text, voice, photo" />
        <MetricCard label="CTR" value={formatPercent(summary.kpis.ctr)} note="clicks / impressions" />
        <MetricCard
          label="No-result rate"
          value={formatPercent(summary.kpis.no_result_rate)}
          note={`${formatNumber(summary.kpis.no_results)} failed searches`}
        />
      </section>

      <section className="grid-12">
        <div className="panel panel-large span-8">
          <PanelHeader
            title="Demand and engagement"
            caption="Searches, impressions and clicks by day"
          />
          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={summary.time_series}>
                <defs>
                  <linearGradient id="searches" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="5%" stopColor="#1f7a54" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#1f7a54" stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="impressions" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="5%" stopColor="#1f5c99" stopOpacity={0.32} />
                    <stop offset="95%" stopColor="#1f5c99" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#e7e0d2" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tickFormatter={formatDate} tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} width={36} />
                <Tooltip content={<ChartTooltip />} />
                <Area
                  dataKey="impressions"
                  name="Impressions"
                  type="monotone"
                  stroke="#1f5c99"
                  fill="url(#impressions)"
                  strokeWidth={2}
                />
                <Area
                  dataKey="searches"
                  name="Searches"
                  type="monotone"
                  stroke="#1f7a54"
                  fill="url(#searches)"
                  strokeWidth={2}
                />
                <Line dataKey="clicks" name="Clicks" stroke="#c57a1b" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel span-4">
          <PanelHeader title="Funnel" caption="Search to product click path" />
          <div className="chart chart-small">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={conversion} layout="vertical" margin={{ left: 18 }}>
                <CartesianGrid stroke="#e7e0d2" strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" hide />
                <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} width={82} />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="value" radius={[0, 5, 5, 0]} fill="#1f7a54" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mini-metrics">
            <span>Consent active</span>
            <strong>{formatNumber(summary.kpis.active_consents)}</strong>
          </div>
        </div>
      </section>

      <section className="grid-12">
        <div className="panel span-5">
          <PanelHeader title="Top queries" caption="What users ask for most often" />
          <div className="table-list">
            {summary.top_queries.map((item, index) => (
              <div className="table-row" key={item.query}>
                <span className="rank">{index + 1}</span>
                <div>
                  <strong>{item.query}</strong>
                  <small>{formatPercent(item.no_result_rate)} no-result</small>
                </div>
                <b>{formatNumber(item.searches)}</b>
              </div>
            ))}
            {summary.top_queries.length === 0 ? <EmptyState label="No query data yet" /> : null}
          </div>
        </div>

        <div className="panel span-7">
          <PanelHeader title="Product performance" caption="Clicked and viewed cards" />
          <div className="product-list">
            {summary.top_products.map((product, index) => (
              <a className="product-row" href={product.url} key={product.id} rel="noreferrer" target="_blank">
                <span className="rank">{index + 1}</span>
                <div className="product-image">
                  {product.cover_image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img alt="" src={product.cover_image_url} />
                  ) : (
                    <span />
                  )}
                </div>
                <div className="product-main">
                  <strong>{product.title}</strong>
                  <small>
                    {formatNumber(product.impressions)} impressions · {formatNumber(product.clicks)} clicks
                  </small>
                </div>
                <b>{formatPercent(product.ctr)}</b>
              </a>
            ))}
            {summary.top_products.length === 0 ? <EmptyState label="No product events yet" /> : null}
          </div>
        </div>
      </section>

      <section className="grid-12">
        <ChartPanel title="Event mix" caption="All tracked event types" data={summary.event_mix} />
        <ChartPanel title="Languages" caption="Telegram language split" data={summary.languages} />
        <ChartPanel title="Input types" caption="Text, photo, voice and clicks" data={summary.input_types} />
      </section>
    </main>
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

function ChartPanel({ title, caption, data }: { title: string; caption: string; data: NamedValue[] }) {
  return (
    <div className="panel span-4">
      <PanelHeader title={title} caption={caption} />
      <div className="chart chart-small">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data.slice(0, 6)} dataKey="value" innerRadius={52} outerRadius={80} paddingAngle={2}>
              {data.slice(0, 6).map((entry, index) => (
                <Cell fill={CHART_COLORS[index % CHART_COLORS.length]} key={entry.name} />
              ))}
            </Pie>
            <Tooltip content={<ChartTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="legend-list">
        {data.slice(0, 5).map((item, index) => (
          <span key={item.name}>
            <i style={{ background: CHART_COLORS[index % CHART_COLORS.length] }} />
            {item.name}
            <b>{formatNumber(item.value)}</b>
          </span>
        ))}
      </div>
      {data.length === 0 ? <EmptyState label="No data yet" /> : null}
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return <p className="empty-state">{label}</p>;
}

function ChartTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload?.length) {
    return null;
  }
  return (
    <div className="chart-tooltip">
      {label ? <strong>{String(label).includes("-") ? formatDate(String(label)) : label}</strong> : null}
      {payload.map((entry) => (
        <span key={entry.name}>
          {entry.name}: <b>{formatNumber(Number(entry.value ?? 0))}</b>
        </span>
      ))}
    </div>
  );
}

type TooltipProps = {
  active?: boolean;
  label?: string;
  payload?: Array<{
    name?: string;
    value?: number | string;
  }>;
};
