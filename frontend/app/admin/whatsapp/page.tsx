"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import WhatsAppInboxDashboard from "@/components/dashboard/whatsapp/WhatsAppInboxDashboard";

// El inbox está permitido para admin y vendedor. La validación de rol vive acá además de
// ocultar el link en el Sidebar (ocultar no alcanza como control de acceso).
const ALLOWED_ROLES = ["admin", "vendedor"];

export default function WhatsAppInboxPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user && !ALLOWED_ROLES.includes(user.role)) {
      router.push("/admin/sales");
    }
  }, [user, loading, router]);

  if (loading || !user || !ALLOWED_ROLES.includes(user.role)) {
    return null;
  }

  return <WhatsAppInboxDashboard />;
}
