import NoraDashboard from "@/components/dashboard/NoraDashboard";

export default function NoraAdminPage() {
    return (
        <main className="min-h-screen py-12 bg-gray-50">
            <div className="w-full max-w-[1800px] mx-auto px-4 md:px-8">
                <div className="mb-8">
                    <h1 className="text-3xl font-extrabold text-gray-900">Waitlist NORA</h1>
                    <p className="text-gray-500 mt-2">Gestiona los prospectos interesados en la línea premium NORA.</p>
                </div>

                <NoraDashboard />
            </div>
        </main>
    );
}
