import SellerDashboard from "@/components/dashboard/SellerDashboard";

export default function SalesManagementPage() {
    return (
        <main className="min-h-screen py-12 bg-gray-50">
            <div className="w-full max-w-[1800px] mx-auto px-4 md:px-8">
                <div className="mb-8">
                    <h1 className="text-3xl font-extrabold text-gray-900">Panel de Ventas</h1>
                    <p className="text-gray-500 mt-2">Gestiona tus leads y realiza seguimiento personalizado.</p>
                </div>

                <SellerDashboard />
            </div>
        </main>
    );
}
