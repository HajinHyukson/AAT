import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AAT Driver Table",
  description: "Single-stock attribution driver table",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
