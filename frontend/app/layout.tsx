import type { Metadata } from "next";
import { Inter, Geist_Mono } from "next/font/google";
import { Analytics } from '@vercel/analytics/next';
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800", "900"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "QuantForge Alpha - Institutional Options Intelligence & Quantitative Research",
  description: "Democratizing institutional-grade options intelligence and quantitative research tools. Real-time dealer positioning, GEX/DEX analysis, implied volatility surfaces, and machine learning signals.",
  keywords: ["options intelligence", "quant research", "gamma exposure", "GEX", "DEX", "NIFTY options", "derivatives analytics", "implied volatility surface", "machine learning trading"],
  authors: [{ name: "Abha Mahato" }]
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${geistMono.variable} antialiased`}>
        {children}
        <Analytics />
      </body>
    </html>
  );
}
