import UserManagement from "@/components/dashboard/UserManagement";

export default function UsersAdminPage() {
    return (
        <main className="min-h-screen py-12 bg-gray-50 flex items-start justify-center">
            <div className="w-full max-w-5xl px-4 md:px-8">
                <div className="mb-8">
                    <h1 className="text-3xl font-extrabold text-gray-900">Personal y Seguridad</h1>
                    <p className="text-gray-500 mt-2">Administra los accesos de tu equipo o cambia tu contraseña de forma segura.</p>
                </div>

                <UserManagement />
            </div>
        </main>
    );
}
