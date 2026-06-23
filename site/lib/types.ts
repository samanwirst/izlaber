export type KPISet = {
  users: number;
  searches: number;
  no_results: number;
  impressions: number;
  clicks: number;
  ctr: number;
  sponsored_impressions: number;
  sponsored_clicks: number;
  sponsored_ctr: number;
  active_sponsored_campaigns: number;
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
  sponsored_impressions: number;
  sponsored_clicks: number;
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

export type SponsoredCampaignStatus = "draft" | "active" | "paused" | "finished";

export type SponsoredCampaignProduct = {
  id: number;
  source_product_id: string | null;
  canonical_url: string;
  title: string;
  brand: string | null;
  category_path_text: string | null;
  rating: string | null;
  reviews_count: number | null;
  current_price: string | null;
  old_price: string | null;
  currency: string;
  availability: string;
  cover_image_url: string | null;
  last_seen_at: string;
  is_active: boolean;
};

export type SponsoredCampaign = {
  id: number;
  name: string;
  advertiser_name: string;
  product: SponsoredCampaignProduct;
  keywords: string[];
  language_codes: string[];
  status: SponsoredCampaignStatus;
  priority: number;
  starts_at: string | null;
  ends_at: string | null;
  daily_impression_limit: number | null;
  total_impression_limit: number | null;
  notes: string;
  metadata: Record<string, unknown>;
  impressions: number;
  clicks: number;
  ctr: number;
  remaining_total_impressions: number | null;
  created_at: string;
  updated_at: string;
};
