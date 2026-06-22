export default function Loading() {
  return (
    <main className="dashboard-shell">
      <section className="topbar skeleton-block" />
      <section className="kpi-grid">
        {Array.from({ length: 4 }).map((_, index) => (
          <div className="metric-card skeleton-block" key={index} />
        ))}
      </section>
      <section className="panel panel-large skeleton-block" />
    </main>
  );
}
