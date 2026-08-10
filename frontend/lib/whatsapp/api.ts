// Cliente HTTP del inbox de WhatsApp. Reusa el patrón del proyecto:
// fetch a `${API_URL}` (lib/api) con Bearer de localStorage.
// - Soporta AbortController (cancelar requests obsoletos del polling).
// - No registra JWT ni respuestas completas.
// - Errores tipados (ApiError con status) para que la UI maneje 401/403/404/red.

import {
  ApiError,
  AssignableUser,
  AssignmentHistoryResponse,
  AssignmentResponse,
  ConversationDetail,
  ConversationFilters,
  ConversationListResponse,
  GetMessagesParams,
  LineOut,
  MessagesResponse,
  UnreadCountsResponse,
} from "./types";
import { API_URL } from "../api";

function authHeaders(): Record<string, string> {
  const token =
    typeof window !== "undefined" ? window.localStorage.getItem("token") : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { ...authHeaders() };
  let body: string | undefined;
  if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  const res = await fetch(`${API_URL}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body,
    signal: opts.signal,
  });
  if (!res.ok) {
    let detail = res.statusText || `HTTP ${res.status}`;
    try {
      const parsed: unknown = await res.json();
      if (
        parsed &&
        typeof parsed === "object" &&
        "detail" in parsed &&
        typeof (parsed as { detail: unknown }).detail === "string"
      ) {
        detail = (parsed as { detail: string }).detail;
      }
    } catch {
      // cuerpo no-JSON: se conserva el statusText genérico (nunca crudo/técnico).
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) {
    return undefined as unknown as T;
  }
  return (await res.json()) as T;
}

function buildQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    usp.set(key, String(value));
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export const whatsappApi = {
  getLines(signal?: AbortSignal): Promise<LineOut[]> {
    return request<LineOut[]>("/whatsapp/lines", { signal });
  },

  getConversations(
    filters: ConversationFilters,
    signal?: AbortSignal
  ): Promise<ConversationListResponse> {
    const qs = buildQuery({
      line_id: filters.line_id ?? undefined,
      assigned_to_me: filters.assigned_to_me ? true : undefined,
      unassigned: filters.unassigned ? true : undefined,
      unread_only: filters.unread_only ? true : undefined,
      status: filters.status ?? undefined,
      search: filters.search ?? undefined,
      limit: filters.limit ?? undefined,
      offset: filters.offset ?? undefined,
    });
    return request<ConversationListResponse>(`/whatsapp/conversations${qs}`, { signal });
  },

  getConversation(id: number, signal?: AbortSignal): Promise<ConversationDetail> {
    return request<ConversationDetail>(`/whatsapp/conversations/${id}`, { signal });
  },

  getMessages(
    id: number,
    params: GetMessagesParams,
    signal?: AbortSignal
  ): Promise<MessagesResponse> {
    const qs = buildQuery({
      direction: params.direction ?? undefined,
      cursor: params.cursor ?? undefined,
      limit: params.limit ?? undefined,
    });
    return request<MessagesResponse>(`/whatsapp/conversations/${id}/messages${qs}`, { signal });
  },

  getUnreadCounts(signal?: AbortSignal): Promise<UnreadCountsResponse> {
    return request<UnreadCountsResponse>("/whatsapp/unread-counts", { signal });
  },

  markRead(id: number, lastReadMessageId: number): Promise<{ conversation_id: number; last_read_message_id: number | null; unread_count: number }> {
    return request(`/whatsapp/conversations/${id}/read`, {
      method: "POST",
      body: { last_read_message_id: lastReadMessageId },
    });
  },

  getAssignments(id: number, signal?: AbortSignal): Promise<AssignmentHistoryResponse> {
    return request<AssignmentHistoryResponse>(`/whatsapp/conversations/${id}/assignments`, { signal });
  },

  assign(id: number, assignedUserId: number, reason?: string | null): Promise<AssignmentResponse> {
    return request<AssignmentResponse>(`/whatsapp/conversations/${id}/assignment`, {
      method: "PATCH",
      body: { assigned_user_id: assignedUserId, reason: reason ?? null },
    });
  },

  // Usuarios asignables: endpoint dedicado admin-only que devuelve SOLO id/full_name/role
  // (sin email ni otros datos). El inbox ya no usa GET /users/.
  getAssignableUsers(signal?: AbortSignal): Promise<AssignableUser[]> {
    return request<AssignableUser[]>("/whatsapp/assignable-users", { signal });
  },
};
