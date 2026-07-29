"use client";

// Capa de datos del inbox: líneas, usuarios asignables (admin), no leídos y la lista de
// conversaciones con paginación incremental REAL por offset (soporta >100), polling con
// merge/dedup por conversation_id, recuperación de cargas iniciales y control de requests
// superpuestos (AbortController + guards). No renderiza; expone estado y acciones.

import { useCallback, useEffect, useRef, useState } from "react";
import { whatsappApi } from "./api";
import {
  ApiError,
  AssignableUser,
  ConversationFilters,
  ConversationListItem,
  InboxFilterState,
  LineOut,
  UnreadCountsResponse,
} from "./types";
import { userDisplayName } from "./format";

const CONV_PAGE = 30;
const CONV_POLL_MAX = 100;
const POLL_UNREAD_MS = 10000;
const POLL_CONVERSATIONS_MS = 7000;

const DEFAULT_FILTERS: InboxFilterState = {
  lineId: null,
  bucket: "all",
  unreadOnly: false,
  status: "",
  search: "",
};

function toApiFilters(f: InboxFilterState, limit: number, offset: number): ConversationFilters {
  return {
    line_id: f.lineId,
    assigned_to_me: f.bucket === "mine",
    unassigned: f.bucket === "unassigned",
    unread_only: f.unreadOnly,
    status: f.status || null,
    search: f.search.trim() ? f.search.trim() : undefined,
    limit,
    offset,
  };
}

function convSignature(items: ConversationListItem[]): string {
  return items
    .map(
      (c) =>
        `${c.conversation_id}:${c.unread_count}:${c.last_message_at ?? ""}:${
          c.assigned_user?.id ?? 0
        }:${c.status}:${c.last_message_preview ?? ""}`
    )
    .join("|");
}

function isAbort(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

export interface InboxData {
  filters: InboxFilterState;
  setFilters: (f: InboxFilterState) => void;
  lines: LineOut[];
  loadingLines: boolean;
  linesError: boolean;
  assignableUsers: AssignableUser[];
  unread: UnreadCountsResponse | null;
  conversations: ConversationListItem[];
  loadingConversations: boolean;
  loadingMore: boolean;
  hasMore: boolean;
  connError: boolean;
  lastUpdated: Date | null;
  loadMore: () => void;
  refresh: () => void;
  retryInitial: () => void;
  updateConversationUnread: (convId: number, unread: number) => void;
  removeConversation: (convId: number) => void;
  noteActivity: () => void;
  nameFor: (id: number | null) => string;
}

export function useWhatsAppInboxData(
  isAdmin: boolean,
  onUnauthorized: () => void
): InboxData {
  const [filters, setFilters] = useState<InboxFilterState>(DEFAULT_FILTERS);
  const [lines, setLines] = useState<LineOut[]>([]);
  const [loadingLines, setLoadingLines] = useState(true);
  const [linesError, setLinesError] = useState(false);
  const [assignableUsers, setAssignableUsers] = useState<AssignableUser[]>([]);
  const [unread, setUnread] = useState<UnreadCountsResponse | null>(null);
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [connError, setConnError] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const filtersRef = useRef(filters);
  const convItemsRef = useRef<ConversationListItem[]>([]);
  const convSigRef = useRef("");
  const connFailRef = useRef(0);
  const linesLoadedRef = useRef(false);
  const assignableLoadedRef = useRef(false);

  const linesAbortRef = useRef<AbortController | null>(null);
  const assignAbortRef = useRef<AbortController | null>(null);
  const unreadAbortRef = useRef<AbortController | null>(null);
  const convAbortRef = useRef<AbortController | null>(null);
  const unreadInFlightRef = useRef(false);
  const convPollInFlightRef = useRef(false);

  useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);
  useEffect(() => {
    convItemsRef.current = conversations;
  }, [conversations]);

  const noteConnOk = useCallback(() => {
    connFailRef.current = 0;
    setConnError(false);
    setLastUpdated(new Date());
  }, []);

  const handleSilent = useCallback(
    (e: unknown) => {
      if (isAbort(e)) return;
      if (e instanceof ApiError) {
        if (e.status === 401) onUnauthorized();
        return; // 4xx no es un problema de red
      }
      connFailRef.current += 1;
      if (connFailRef.current >= 2) setConnError(true);
    },
    [onUnauthorized]
  );

  const nameFor = useCallback(
    (id: number | null): string => {
      if (id === null || id === undefined) return "—";
      const u = assignableUsers.find((x) => x.id === id);
      return u ? userDisplayName(u.full_name, u.id) : `Usuario #${id}`;
    },
    [assignableUsers]
  );

  const fetchLines = useCallback(async () => {
    linesAbortRef.current?.abort();
    const ac = new AbortController();
    linesAbortRef.current = ac;
    setLoadingLines(true);
    try {
      const l = await whatsappApi.getLines(ac.signal);
      setLines(l);
      setLinesError(false);
      linesLoadedRef.current = true;
      noteConnOk();
    } catch (e) {
      if (isAbort(e)) return;
      if (e instanceof ApiError && e.status === 401) {
        onUnauthorized();
        return;
      }
      // Fallo de red / servidor: NO es "sin líneas".
      setLinesError(true);
      handleSilent(e);
    } finally {
      if (linesAbortRef.current === ac) setLoadingLines(false);
    }
  }, [handleSilent, noteConnOk, onUnauthorized]);

  const fetchAssignable = useCallback(async () => {
    if (!isAdmin) return;
    assignAbortRef.current?.abort();
    const ac = new AbortController();
    assignAbortRef.current = ac;
    try {
      const u = await whatsappApi.getAssignableUsers(ac.signal);
      setAssignableUsers(u);
      assignableLoadedRef.current = true;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) onUnauthorized();
      // en otros casos el selector queda vacío; se reintenta con "Actualizar".
    }
  }, [isAdmin, onUnauthorized]);

  const fetchUnread = useCallback(async () => {
    if (unreadInFlightRef.current) return;
    unreadInFlightRef.current = true;
    unreadAbortRef.current?.abort();
    const ac = new AbortController();
    unreadAbortRef.current = ac;
    try {
      const u = await whatsappApi.getUnreadCounts(ac.signal);
      setUnread(u);
      noteConnOk();
    } catch (e) {
      handleSilent(e);
    } finally {
      unreadInFlightRef.current = false;
    }
  }, [handleSilent, noteConnOk]);

  const reloadConversations = useCallback(async () => {
    convAbortRef.current?.abort();
    const ac = new AbortController();
    convAbortRef.current = ac;
    setLoadingConversations(true);
    try {
      const resp = await whatsappApi.getConversations(
        toApiFilters(filtersRef.current, CONV_PAGE, 0),
        ac.signal
      );
      convSigRef.current = convSignature(resp.items);
      setConversations(resp.items);
      setHasMore(resp.has_more);
      noteConnOk();
    } catch (e) {
      handleSilent(e);
    } finally {
      if (convAbortRef.current === ac) setLoadingConversations(false);
    }
  }, [handleSilent, noteConnOk]);

  const pollConversations = useCallback(async () => {
    if (convPollInFlightRef.current) return;
    convPollInFlightRef.current = true;
    try {
      const limit = Math.min(
        CONV_POLL_MAX,
        Math.max(CONV_PAGE, convItemsRef.current.length)
      );
      const resp = await whatsappApi.getConversations(
        toApiFilters(filtersRef.current, limit, 0)
      );
      // Merge: la primera ventana fresca arriba (actualizada/reordenada/nueva) + el resto
      // de lo ya cargado sin duplicar por conversation_id.
      const freshIds = new Set(resp.items.map((c) => c.conversation_id));
      const tail = convItemsRef.current.filter((c) => !freshIds.has(c.conversation_id));
      const merged = [...resp.items, ...tail];
      const sig = convSignature(merged);
      if (sig !== convSigRef.current) {
        convSigRef.current = sig;
        setConversations(merged);
      }
      noteConnOk();
    } catch (e) {
      handleSilent(e);
    } finally {
      convPollInFlightRef.current = false;
    }
  }, [handleSilent, noteConnOk]);

  const loadMore = useCallback(async () => {
    setLoadingMore(true);
    try {
      const offset = convItemsRef.current.length;
      const resp = await whatsappApi.getConversations(
        toApiFilters(filtersRef.current, CONV_PAGE, offset)
      );
      const existing = new Set(convItemsRef.current.map((c) => c.conversation_id));
      const added = resp.items.filter((c) => !existing.has(c.conversation_id));
      const merged = [...convItemsRef.current, ...added];
      convSigRef.current = convSignature(merged);
      setConversations(merged);
      setHasMore(resp.has_more);
      noteConnOk();
    } catch (e) {
      handleSilent(e);
    } finally {
      setLoadingMore(false);
    }
  }, [handleSilent, noteConnOk]);

  const updateConversationUnread = useCallback((convId: number, unreadCount: number) => {
    setConversations((prev) => {
      const next = prev.map((c) =>
        c.conversation_id === convId ? { ...c, unread_count: unreadCount } : c
      );
      convSigRef.current = convSignature(next);
      return next;
    });
  }, []);

  const removeConversation = useCallback((convId: number) => {
    setConversations((prev) => {
      const next = prev.filter((c) => c.conversation_id !== convId);
      convSigRef.current = convSignature(next);
      return next;
    });
  }, []);

  const refresh = useCallback(() => {
    fetchUnread();
    pollConversations();
  }, [fetchUnread, pollConversations]);

  const retryInitial = useCallback(() => {
    if (!linesLoadedRef.current || linesError) fetchLines();
    if (isAdmin && !assignableLoadedRef.current) fetchAssignable();
    refresh();
  }, [fetchAssignable, fetchLines, isAdmin, linesError, refresh]);

  // --- Carga inicial ---
  useEffect(() => {
    fetchLines();
    fetchAssignable();
    fetchUnread();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Reload de conversaciones ante cambios de filtros (debounce) ---
  useEffect(() => {
    const t = setTimeout(() => {
      reloadConversations();
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  // --- Polling (pausado con pestaña oculta) ---
  useEffect(() => {
    const hidden = () => typeof document !== "undefined" && document.hidden;
    const u = setInterval(() => {
      if (!hidden()) fetchUnread();
    }, POLL_UNREAD_MS);
    const c = setInterval(() => {
      if (!hidden()) pollConversations();
    }, POLL_CONVERSATIONS_MS);
    return () => {
      clearInterval(u);
      clearInterval(c);
    };
  }, [fetchUnread, pollConversations]);

  // --- Cleanup de controladores ---
  useEffect(() => {
    return () => {
      linesAbortRef.current?.abort();
      assignAbortRef.current?.abort();
      unreadAbortRef.current?.abort();
      convAbortRef.current?.abort();
    };
  }, []);

  return {
    filters,
    setFilters,
    lines,
    loadingLines,
    linesError,
    assignableUsers,
    unread,
    conversations,
    loadingConversations,
    loadingMore,
    hasMore,
    connError,
    lastUpdated,
    loadMore,
    refresh,
    retryInitial,
    updateConversationUnread,
    removeConversation,
    noteActivity: noteConnOk,
    nameFor,
  };
}
