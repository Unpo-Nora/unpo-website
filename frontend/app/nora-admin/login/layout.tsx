import type { Metadata } from "next";

// Server Component: aporta metadata propia al login NORA.
// (nora-admin/layout.tsx es Client Component y no puede exportar metadata.)
export const metadata: Metadata = {
    title: "Ingresar — CRM NORA",
};

export default function NoraLoginLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return <>{children}</>;
}
