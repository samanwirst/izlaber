import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Izlaber Analytics",
  description: "Professional analytics dashboard for Izlaber marketplace intelligence.",
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
