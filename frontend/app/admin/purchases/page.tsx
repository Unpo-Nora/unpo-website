import PurchasesDashboard from "@/components/dashboard/PurchasesDashboard";

export default function PurchasesPage() {
    return (
        <main className="min-h-screen py-12 bg-gray-50 flex items-start justify-center">
            <div className="w-full max-w-5xl px-4 md:px-8">
                <PurchasesDashboard />
            </div>
        </main>
    );
}
