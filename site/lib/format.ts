export function formatNumber(value: number): string {
  return new Intl.NumberFormat("ru-RU").format(value);
}

export function formatPercent(value: number): string {
  return `${new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 1,
    minimumFractionDigits: value > 0 && value < 1 ? 1 : 0,
  }).format(value)}%`;
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
  }).format(new Date(value));
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
