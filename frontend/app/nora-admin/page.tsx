import type { Metadata } from "next";
import NoraProspectsPanel from "@/components/nora/NoraProspectsPanel";

export const metadata: Metadata = {
    title: "Prospectos · NORA",
};

// Panel principal del CRM NORA: un único panel comercial de prospectos
// (estilo Clienty). El shell (layout) ya provee contenedor, padding y branding.
export default function NoraAdminPage() {
    return <NoraProspectsPanel />;
}
