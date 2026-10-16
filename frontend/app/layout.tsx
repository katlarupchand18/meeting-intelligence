import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Meeting Intelligence",
    template: "%s | Meeting Intelligence",
  },
  description:
    "AI-powered meeting intelligence that transforms conversations into summaries, decisions, commitments, evidence, and actionable insights.",
  applicationName: "Meeting Intelligence",
  keywords: [
    "Meeting Intelligence",
    "AI Meeting Assistant",
    "Meeting Summaries",
    "Decision Tracking",
    "Action Items",
    "Meeting Accountability",
    "Transcript Analysis",
  ],
  robots: {
    index: false,
    follow: false,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f5f7fb",
  colorScheme: "light",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}