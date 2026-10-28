import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { cn } from "@/lib/utils";
import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "Aegis | Data boundary control plane",
  description:
    "See exactly what crossed your model boundary, post-scrub.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={cn("dark font-sans antialiased", geist.variable)}>
      <body className="min-h-screen bg-background text-foreground">
        {children}
      </body>
    </html>
  );
}
