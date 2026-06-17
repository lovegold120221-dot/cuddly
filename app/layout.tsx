import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vision Agents Demo",
  description: "Real-time AI Agents with Stream and Vercel",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
