import type { Metadata } from "next";
import { Poppins, Geist_Mono } from "next/font/google";
import "./globals.css";

const poppins = Poppins({
  variable: "--font-poppins",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800", "900"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "QuantForge AI - Institutional Options Intelligence & Quantitative Research",
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
    <html
      lang="en"
      className={`${poppins.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full bg-[#ebedef] text-slate-800 flex flex-col font-sans" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
