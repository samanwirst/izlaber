"use client";

export default function Error({ error }: { error: Error & { digest?: string } }) {
  return (
    <main className="error-shell">
      <section className="error-panel">
        <p className="eyebrow">Analytics unavailable</p>
        <h1>Не удалось загрузить аналитику</h1>
        <p>{error.message}</p>
      </section>
    </main>
  );
}
