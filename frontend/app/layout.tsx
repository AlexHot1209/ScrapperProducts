import type { Metadata } from "next";
import type { ReactNode } from "react";
import { QueryProvider } from "@/lib/query-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mythos Garden",
  description: "Cautare dinamica de produse pe site-uri din Romania."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ro">
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
