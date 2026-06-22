import { AnalyticsDashboard } from "./components/AnalyticsDashboard";
import { getAnalyticsSummary } from "../lib/api";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function Home() {
  const summary = await getAnalyticsSummary(30);
  return <AnalyticsDashboard summary={summary} />;
}
