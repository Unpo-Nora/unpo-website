"use client";

import { useAuth } from "@/context/AuthContext";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Loader2, Menu } from "lucide-react";

import Sidebar from "@/components/dashboard/Sidebar";

export default function AdminLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const { user, loading } = useAuth();
    const router = useRouter();
    const pathname = usePathname();

    const [sidebarOpen, setSidebarOpen] = useState(false);

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

    // Close the sidebar when navigating to a different page on mobile
    useEffect(() => {
        setSidebarOpen(false);
    }, [pathname]);

    // Lock background scroll while the mobile drawer is open; restore on close/unmount
    useEffect(() => {
        if (!sidebarOpen) return;
        const previous = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        return () => {
            document.body.style.overflow = previous;
        };
    }, [sidebarOpen]);

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
        <div className="min-h-screen flex overflow-hidden bg-slate-50">
            <Sidebar isOpen={sidebarOpen} setIsOpen={setSidebarOpen} />
            
            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
                {/* Mobile Header */}
                <header className="lg:hidden bg-white border-b border-slate-200 px-4 py-4 flex items-center justify-between shadow-sm z-10 w-full shrink-0">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-red-600 rounded flex items-center justify-center text-white font-bold italic shrink-0">
                            U
                        </div>
                        <h1 className="font-bold text-slate-800 tracking-tight truncate">UNPO Control Center</h1>
                    </div>
                    <button onClick={() => setSidebarOpen(true)} className="p-2 -mr-2 text-slate-600 hover:bg-slate-100 rounded-lg shrink-0">
                        <Menu size={24} />
                    </button>
                </header>

                <main className={`flex-1 ${sidebarOpen ? "overflow-hidden lg:overflow-y-auto" : "overflow-y-auto"} p-4 sm:p-8 lg:p-12 relative`}>
                    <div className="w-full max-w-[1800px] mx-auto">
                        {children}
                    </div>
                </main>
            </div>

            {/* Overlay for mobile sidebar */}
            {sidebarOpen && (
                <div 
                    className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-40 lg:hidden"
                    onClick={() => setSidebarOpen(false)}
                />
            )}
        </div>
    );
}
