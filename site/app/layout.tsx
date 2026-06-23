import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Izlaber Analytics",
  description:
    "Аналитика поисков, карточек и переходов Izlaber: популярные запросы, языки, типы поиска, клики по товарам и динамика активности.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
