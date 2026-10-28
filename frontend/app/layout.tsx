import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { cn } from "@/lib/utils";
import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "Aegis | Data boundary control plane",
  description:
    "See exactly what crossed your model boundary, post-scrub.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={cn("dark font-sans antialiased", geist.variable, geistMono.variable)}>
      <body className="min-h-screen bg-background text-foreground">
        {children}
      </body>
    </html>
  );
}
