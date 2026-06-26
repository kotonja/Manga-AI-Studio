import type { Metadata } from "next";
import type { ReactNode } from "react";

import { CommandCenterBar } from "@/components/commands/command-center-bar";
import { FeedbackButton } from "@/components/feedback/feedback-button";
import "./globals.css";

export const metadata: Metadata = {
  title: "Manga AI Studio",
  description: "AI manga creation workspace"
};

export default function RootLayout({
  children
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        {children}
        <CommandCenterBar />
        <FeedbackButton />
      </body>
    </html>
  );
}
