import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: {
    default: "EcoTrack — Planetary Environmental Intelligence",
    template: "%s | EcoTrack",
  },
  description:
    "AI-for-Earth platform providing climate analytics, biodiversity monitoring, public health insights, food security forecasting, and resource equity optimization across 180+ countries.",
  keywords: [
    "environmental intelligence",
    "climate analytics",
    "biodiversity",
    "federated learning",
    "geospatial",
    "AI for Earth",
  ],
  authors: [{ name: "EcoTrack Team" }],
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0f1a" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning className={inter.variable}>
      <body className={`${inter.className} antialiased`}>{children}</body>
    </html>
  );
}
