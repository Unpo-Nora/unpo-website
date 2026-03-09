"use client";

import { useAuth } from "@/context/AuthContext";
import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import { Loader2 } from "lucide-react";

import Sidebar from "@/components/dashboard/Sidebar";

export default function AdminLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const { user, loading } = useAuth();
    const router = useRouter();
    const pathname = usePathname();

    useEffect(() => {
        if (!loading) {
            if (!user && pathname !== "/admin/login") {
                router.push("/admin/login");
            } else if (user && pathname === "/admin/login") {
                router.push("/admin/sales");
            }

            // Role-based protection
            if (user && pathname === "/admin/import" && user.role !== 'admin') {
                router.push("/admin/sales"); // Vendedores no pueden entrar a importar
            }
        }
    }, [user, loading, router, pathname]);

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
                <Loader2 className="animate-spin text-blue-600" size={48} />
            </div>
        );
    }

    const isLoginPage = pathname === "/admin/login";

    if (!user && !isLoginPage) {
        return null;
    }

    if (isLoginPage) {
        return <>{children}</>;
    }

    return (
        <div className="min-h-screen flex overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-y-auto p-8 lg:p-12">
                <div className="w-full max-w-[1800px] mx-auto">
                    {children}
                </div>
            </main>
        </div>
    );
}
