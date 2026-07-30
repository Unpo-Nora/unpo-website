// Helpers de formato (fecha/hora legible, etiqueta de contacto, tipo de mensaje).
// No exponen datos sensibles: el teléfono ya llega enmascarado desde el backend.

import { ContactOut } from "./types";

export function formatMessageTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
}

export function formatConversationTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" });
}

export function formatFullDateTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function contactLabel(contact: ContactOut | null | undefined, fallbackId?: number): string {
  if (contact) {
    if (contact.display_name && contact.display_name.trim()) return contact.display_name;
    if (contact.phone_masked && contact.phone_masked.trim()) return contact.phone_masked;
    return `Contacto #${contact.id}`;
  }
  return fallbackId ? `Contacto #${fallbackId}` : "Contacto";
}

const MESSAGE_TYPE_LABELS: Record<string, string> = {
  text: "Texto",
  image: "Imagen",
  audio: "Audio",
  video: "Video",
  document: "Documento",
  sticker: "Sticker",
  location: "Ubicación",
  contacts: "Contacto",
};

export function messageTypeLabel(type: string): string {
  return MESSAGE_TYPE_LABELS[type] ?? type;
}

const CONVERSATION_STATUS_LABELS: Record<string, string> = {
  open: "Abierta",
  closed: "Cerrada",
  archived: "Archivada",
};

export function conversationStatusLabel(status: string): string {
  return CONVERSATION_STATUS_LABELS[status] ?? status;
}

export function userDisplayName(fullName: string | null | undefined, id: number | null | undefined): string {
  if (fullName && fullName.trim()) return fullName;
  if (id !== null && id !== undefined) return `Usuario #${id}`;
  return "—";
}
