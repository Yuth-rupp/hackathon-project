import type { Metadata, Viewport } from "next";
import { Inter, Noto_Sans_Khmer } from "next/font/google";
import "./globals.css";
import { LanguageProvider } from "@/context/LanguageContext";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const notoSansKhmer = Noto_Sans_Khmer({
  subsets: ["khmer"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-khmer",
  display: "swap",
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  title: "FloodPulse AI | Tonle Sap Flood Intelligence & Early Warning",
  description:
    "Advanced hydrological monitoring, AI flood hazard prediction, and early warning platform for Tonle Sap Lake Basin, Cambodia.",
  keywords: [
    "Tonle Sap",
    "Flood Monitoring",
    "Cambodia",
    "Hydrology",
    "Earth Observation",
    "Early Warning System",
    "Open-Meteo",
    "Copernicus Sentinel",
  ],
  authors: [{ name: "FloodPulse AI Research Team" }],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
          crossOrigin=""
        />
      </head>
      <body
        className={`${inter.variable} ${notoSansKhmer.variable} font-sans bg-navy-950 text-slate-100 antialiased selection:bg-cyan-500 selection:text-white`}
      >
        <LanguageProvider>{children}</LanguageProvider>
      </body>
    </html>
  );
}
