export type KPISet = {
  users: number;
  searches: number;
  no_results: number;
  impressions: number;
  clicks: number;
  ctr: number;
  no_result_rate: number;
  active_consents: number;
};

export type TimeSeriesPoint = {
  date: string;
  users: number;
  searches: number;
  no_results: number;
  impressions: number;
  clicks: number;
};

export type NamedValue = {
  name: string;
  value: number;
};

export type TopQuery = {
  query: string;
  searches: number;
  no_results: number;
  no_result_rate: number;
};

export type TopProduct = {
  id: number;
  title: string;
  url: string;
  cover_image_url: string;
  impressions: number;
  clicks: number;
  ctr: number;
};

export type ConsentSummary = {
  active: number;
  declined: number;
  revoked: number;
  total: number;
};

export type AnalyticsSummary = {
  period: {
    days: number;
    from: string;
    to: string;
  };
  kpis: KPISet;
  time_series: TimeSeriesPoint[];
  event_mix: NamedValue[];
  top_queries: TopQuery[];
  top_products: TopProduct[];
  languages: NamedValue[];
  input_types: NamedValue[];
  consents: ConsentSummary;
  generated_at: string;
};
