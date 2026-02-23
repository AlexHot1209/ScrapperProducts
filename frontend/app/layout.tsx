import type { Metadata } from "next";
import type { ReactNode } from "react";
import { QueryProvider } from "@/lib/query-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Romania Product Discovery",
  description: "Fast product discovery and scraping across Romanian websites."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
