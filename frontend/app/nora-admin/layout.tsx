"use client";

import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Loader2, Menu } from "lucide-react";

import NoraSidebar from "@/components/dashboard/NoraSidebar";

// Shell propio del CRM NORA. Conceptualmente similar a app/admin/layout.tsx
// pero con branding NORA y NoraSidebar. No toca el shell UNPO.
// Login compartido por ahora: si no hay sesion, redirige a /admin/login.
export default function NoraAdminLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const { user, loading } = useAuth();
    const router = useRouter();

    const [sidebarOpen, setSidebarOpen] = useState(false);

    useEffect(() => {
        if (!loading && !user) {
            router.push("/admin/login");
        }
    }, [user, loading, router]);

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-slate-50">
                <Loader2 className="animate-spin text-slate-900" size={48} />
            </div>
        );
    }

    if (!user) {
        return null;
    }

    return (
        <div className="min-h-screen flex overflow-hidden bg-slate-50">
            <NoraSidebar isOpen={sidebarOpen} setIsOpen={setSidebarOpen} />

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
                {/* Mobile Header - NORA branding */}
                <header className="lg:hidden bg-white border-b border-slate-200 px-4 py-4 flex items-center justify-between shadow-sm z-10 w-full shrink-0">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-slate-900 text-white rounded flex items-center justify-center font-serif font-bold shrink-0">
                            N
                        </div>
                        <h1 className="font-serif font-medium text-slate-800 tracking-wide truncate">NORA</h1>
                    </div>
                    <button onClick={() => setSidebarOpen(true)} className="p-2 -mr-2 text-slate-600 hover:bg-slate-100 rounded-lg shrink-0">
                        <Menu size={24} />
                    </button>
                </header>

                <main className="flex-1 overflow-y-auto p-4 sm:p-8 lg:p-12 relative">
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
