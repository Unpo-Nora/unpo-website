import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
    title: "UNPO Sales System",
    description: "B2B Sales Platform",
};

import { AuthProvider } from "@/context/AuthContext";
import VisitorTracker from "@/components/VisitorTracker";

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en">
            <body className="min-h-[100dvh] bg-gray-50">
                <AuthProvider>
                    <VisitorTracker />
                    {children}
                </AuthProvider>
            </body>
        </html>
    );
}
