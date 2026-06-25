import type { Metadata } from "next";
import NoraDashboard from "@/components/dashboard/NoraDashboard";

export const metadata: Metadata = {
    title: "CRM NORA",
};

export default function NoraAdminPage() {
    return (
        <div className="min-h-screen py-12 bg-slate-50">
            <div className="w-full max-w-[1800px] mx-auto px-4 md:px-8">
                <div className="mb-8">
                    <h1 className="text-3xl font-serif font-medium text-slate-900">CRM NORA</h1>
                    <p className="text-slate-500 mt-2">Gestiona los prospectos interesados en la línea NORA.</p>
                </div>

                <NoraDashboard />
            </div>
        </div>
    );
}
