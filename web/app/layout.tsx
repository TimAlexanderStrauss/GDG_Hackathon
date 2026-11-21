import type { Metadata, Viewport } from "next";
import { Manrope } from "next/font/google";
import "@copilotkit/react-core/v2/styles.css";
import "./globals.css";

const manrope = Manrope({ variable: "--font-manrope", subsets: ["latin"], weight: ["400", "500", "600", "700", "800"] });

export const metadata: Metadata = {
  title: "Sidequest",
  description: "Finds events in public social posts that match your preferences and enrolls you only after your click.",
};

export const viewport: Viewport = {
  themeColor: "#ffffff",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${manrope.variable} h-full antialiased`}>
      <body className="min-h-full">{children}</body>
    </html>
  );
}
