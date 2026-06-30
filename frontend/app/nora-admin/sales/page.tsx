import { redirect } from "next/navigation";

// Consolidación de superficies (Etapa 4.3): el CRM NORA tiene un único panel de
// prospectos en /nora-admin. /nora-admin/sales se mantiene como compat temporal y
// redirige al panel principal; ya no se muestra como opción separada en el sidebar.
export default function NoraSalesRedirect() {
    redirect("/nora-admin");
}
