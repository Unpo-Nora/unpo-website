import ImportDashboard from "@/components/dashboard/ImportDashboard";

export default function ImportPage() {
    return (
        <main className="min-h-screen py-12 bg-gray-50">
            <div className="container mx-auto px-4">
                <div className="mb-8 text-center">
                    <h1 className="text-3xl font-extrabold text-gray-900 sm:text-4xl">
                        Panel de Administración UNPO
                    </h1>
                    <p className="mt-3 max-w-2xl mx-auto text-xl text-gray-500 sm:mt-4">
                        Gestión y carga masiva de leads históricos.
                    </p>
                </div>

                <ImportDashboard />

                <div className="mt-12 text-center text-sm text-gray-400">
                    <p>© 2026 UNPO Ecosystem - Herramientas Internas</p>
                </div>
            </div>
        </main>
    );
}
