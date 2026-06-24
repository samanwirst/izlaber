import { AnalyticsDashboard } from "./components/AnalyticsDashboard";
import { BroadcastConsole } from "./components/BroadcastConsole";
import { LoginGate } from "./components/LoginGate";
import { SponsoredCampaignConsole } from "./components/SponsoredCampaignConsole";
import { logoutAction } from "./auth-actions";
import { getAnalyticsSummary, getSponsoredCampaigns } from "../lib/api";
import { getLoginState } from "../lib/auth";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type HomeProps = {
  searchParams: Promise<{ login?: string }>;
};

export default async function Home({ searchParams }: HomeProps) {
  const [params, loginState] = await Promise.all([searchParams, getLoginState()]);
  if (!loginState.authenticated) {
    return (
      <LoginGate
        adminsConfigured={loginState.adminsConfigured}
        hasChallenge={loginState.hasChallenge}
        message={params.login}
      />
    );
  }

  const [summary, campaigns] = await Promise.all([
    getAnalyticsSummary(30),
    getSponsoredCampaigns(),
  ]);

  return (
    <main>
      <form action={logoutAction} className="logout-form">
        <button type="submit">Logout</button>
      </form>
      <AnalyticsDashboard summary={summary} />
      <SponsoredCampaignConsole campaigns={campaigns} />
      <BroadcastConsole activeConsentCount={summary.kpis.active_consents} />
    </main>
  );
}
