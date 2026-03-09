import ClientsDashboard from "@/components/dashboard/ClientsDashboard";

export default function ClientsManagementPage() {
    return (
        <main className="min-h-screen py-12 bg-gray-50">
            <div className="container mx-auto px-4">
                <div className="mb-8">
                    <h1 className="text-3xl font-extrabold text-gray-900">Cartera de Clientes</h1>
                    <p className="text-gray-500 mt-2">Visualiza el historial de compras y gestiona a tus clientes frecuentes.</p>
                </div>

                <ClientsDashboard />
            </div>
        </main>
    );
}
