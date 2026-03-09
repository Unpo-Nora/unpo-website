import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
    title: "UNPO Sales System",
    description: "B2B Sales Platform",
};

import { AuthProvider } from "@/context/AuthContext";

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en">
            <body className="min-h-screen bg-gray-50">
                <AuthProvider>
                    {children}
                </AuthProvider>
            </body>
        </html>
    );
}
