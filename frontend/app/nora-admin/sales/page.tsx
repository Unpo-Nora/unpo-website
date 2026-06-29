import type { Metadata } from "next";
import NoraSalesPanel from "@/components/nora/NoraSalesPanel";

export const metadata: Metadata = {
    title: "Panel de Ventas NORA",
};

export default function NoraSalesPage() {
    return (
        <div className="min-h-screen py-12 bg-slate-50">
            <div className="w-full max-w-[1800px] mx-auto px-4 md:px-8">
                <NoraSalesPanel />
            </div>
        </div>
    );
}
