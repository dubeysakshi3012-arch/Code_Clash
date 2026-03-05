import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Black_Ops_One, VT323, Barlow_Condensed } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/contexts/AuthContext";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const blackOpsOne = Black_Ops_One({
  variable: "--font-arcade",
  weight: "400",
  subsets: ["latin"],
});

const vt323 = VT323({
  variable: "--font-terminal",
  weight: "400",
  subsets: ["latin"],
});

const barlowCondensed = Barlow_Condensed({
  variable: "--font-condensed",
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CodeClash - Real-Time Competitive Coding",
  description: "War room coding. Assessment-based ELO. Live 1v1 matches. Code or be coded.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} ${blackOpsOne.variable} ${vt323.variable} ${barlowCondensed.variable} antialiased`}
      >
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
