"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { MessageCircle, RefreshCw, Loader2, WifiOff } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { whatsappApi } from "@/lib/whatsapp/api";
import {
  ApiError,
  AssignableUser,
  AssignmentHistoryOut,
  ConversationDetail,
  ConversationFilters,
  ConversationListItem,
  InboxFilterState,
  LineOut,
  MessageOut,
  UnreadCountsResponse,
} from "@/lib/whatsapp/types";
import { formatMessageTime, userDisplayName } from "@/lib/whatsapp/format";
import WhatsAppFilters from "./WhatsAppFilters";
import ConversationList from "./ConversationList";
import ConversationPanel from "./ConversationPanel";
import WhatsAppEmptyState from "./WhatsAppEmptyState";
import UnreadBadge from "./UnreadBadge";

const CONV_PAGE = 30;
const CONV_MAX = 100;
const MESSAGES_PAGE = 50;

const POLL_UNREAD_MS = 10000;
const POLL_CONVERSATIONS_MS = 7000;
const POLL_MESSAGES_MS = 4000;

function toApiFilters(f: InboxFilterState, limit: number): ConversationFilters {
  return {
    line_id: f.lineId,
    assigned_to_me: f.bucket === "mine",
    unassigned: f.bucket === "unassigned",
    unread_only: f.unreadOnly,
    status: f.status || null,
    search: f.search.trim() ? f.search.trim() : undefined,
    limit,
    offset: 0,
  };
}

function compareMsg(a: MessageOut, b: MessageOut): number {
  const ca = a.created_at ?? "";
  const cb = b.created_at ?? "";
  if (ca < cb) return -1;
  if (ca > cb) return 1;
  return a.id - b.id;
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

export default function WhatsAppInboxDashboard() {
  const { user, logout } = useAuth();
  const isAdmin = user?.role === "admin";

  const [lines, setLines] = useState<LineOut[]>([]);
  const [loadingLines, setLoadingLines] = useState(true);
  const [filters, setFilters] = useState<InboxFilterState>({
    lineId: null,
    bucket: "all",
    unreadOnly: false,
    status: "",
    search: "",
  });

  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [convLimit, setConvLimit] = useState(CONV_PAGE);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [olderCursor, setOlderCursor] = useState<string | null>(null);
  const [hasOlder, setHasOlder] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);

  const [unread, setUnread] = useState<UnreadCountsResponse | null>(null);
  const [assignableUsers, setAssignableUsers] = useState<AssignableUser[]>([]);
  const [assigning, setAssigning] = useState(false);
  const [history, setHistory] = useState<AssignmentHistoryOut[]>([]);
  const [historyFailed, setHistoryFailed] = useState(false);

  const [toast, setToast] = useState<{ msg: string; kind: "ok" | "err" } | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [connError, setConnError] = useState(false);
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false);

  // Refs para leer estado fresco dentro del polling / callbacks.
  const filtersRef = useRef(filters);
  const convLimitRef = useRef(convLimit);
  const selectedIdRef = useRef(selectedId);
  const newerCursorRef = useRef<string | null>(null);
  const messageIdsRef = useRef<Set<number>>(new Set());
  const lastMarkedReadRef = useRef(0);
  const convSigRef = useRef("");
  const connFailRef = useRef(0);
  const loadingMessagesRef = useRef(false);
  const convAbortRef = useRef<AbortController | null>(null);
  const msgLoadAbortRef = useRef<AbortController | null>(null);
  const msgPollAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);
  useEffect(() => {
    convLimitRef.current = convLimit;
  }, [convLimit]);
  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);
  useEffect(() => {
    loadingMessagesRef.current = loadingMessages;
  }, [loadingMessages]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  const noteConnOk = useCallback(() => {
    connFailRef.current = 0;
    setConnError(false);
    setLastUpdated(new Date());
  }, []);

  const handleSilentError = useCallback(
    (e: unknown) => {
      if (isAbort(e)) return;
      if (e instanceof ApiError) {
        if (e.status === 401) {
          logout();
          return;
        }
        // 4xx no es un problema de red: no marcar "reconectando".
        return;
      }
      connFailRef.current += 1;
      if (connFailRef.current >= 2) setConnError(true);
    },
    [logout]
  );

  const nameFor = useCallback(
    (id: number | null): string => {
      if (id === null || id === undefined) return "—";
      const u = assignableUsers.find((x) => x.id === id);
      return u ? userDisplayName(u.full_name, u.id) : `Usuario #${id}`;
    },
    [assignableUsers]
  );

  const fetchUnread = useCallback(async () => {
    try {
      const u = await whatsappApi.getUnreadCounts();
      setUnread(u);
      noteConnOk();
    } catch (e) {
      handleSilentError(e);
    }
  }, [handleSilentError, noteConnOk]);

  const fetchConversations = useCallback(
    async (limit: number, opts: { silent?: boolean; more?: boolean } = {}) => {
      convAbortRef.current?.abort();
      const ac = new AbortController();
      convAbortRef.current = ac;
      if (opts.more) setLoadingMore(true);
      else if (!opts.silent) setLoadingConversations(true);
      try {
        const resp = await whatsappApi.getConversations(
          toApiFilters(filtersRef.current, limit),
          ac.signal
        );
        const sig = convSignature(resp.items);
        if (sig !== convSigRef.current) {
          convSigRef.current = sig;
          setConversations(resp.items);
        }
        setHasMore(resp.has_more);
        noteConnOk();
      } catch (e) {
        handleSilentError(e);
      } finally {
        if (convAbortRef.current === ac) {
          setLoadingMore(false);
          setLoadingConversations(false);
        }
      }
    },
    [handleSilentError, noteConnOk]
  );

  const markConversationGone = useCallback((convId: number) => {
    setConversations((prev) => prev.filter((c) => c.conversation_id !== convId));
    if (selectedIdRef.current === convId) {
      setSelectedId(null);
      setDetail(null);
      setMessages([]);
      setMobilePanelOpen(false);
      setToast({ msg: "La conversación ya no está disponible", kind: "err" });
    }
  }, []);

  const maybeMarkRead = useCallback(
    (convId: number, lastMsgId: number | undefined, unreadHint: number) => {
      if (typeof document !== "undefined" && document.hidden) return;
      if (!lastMsgId) return;
      if (lastMsgId <= lastMarkedReadRef.current) return;
      if (unreadHint <= 0) return;
      lastMarkedReadRef.current = lastMsgId;
      whatsappApi
        .markRead(convId, lastMsgId)
        .then((res) => {
          setConversations((prev) =>
            prev.map((c) =>
              c.conversation_id === convId ? { ...c, unread_count: res.unread_count } : c
            )
          );
          setDetail((d) =>
            d && d.conversation_id === convId ? { ...d, unread_count: res.unread_count } : d
          );
          fetchUnread();
        })
        .catch((e) => {
          lastMarkedReadRef.current = 0; // permitir reintento
          if (e instanceof ApiError && e.status === 401) {
            logout();
            return;
          }
          setToast({ msg: "No se pudo marcar como leído", kind: "err" });
        });
    },
    [fetchUnread, logout]
  );

  const loadDetail = useCallback(
    async (id: number) => {
      setLoadingDetail(true);
      try {
        const d = await whatsappApi.getConversation(id);
        if (selectedIdRef.current === id) setDetail(d);
        noteConnOk();
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          markConversationGone(id);
        } else {
          handleSilentError(e);
        }
      } finally {
        setLoadingDetail(false);
      }
    },
    [handleSilentError, markConversationGone, noteConnOk]
  );

  const loadHistory = useCallback(async (id: number) => {
    try {
      const h = await whatsappApi.getAssignments(id);
      if (selectedIdRef.current === id) {
        setHistory(h.items);
        setHistoryFailed(false);
      }
    } catch {
      // No bloquear el panel si falla el historial.
      if (selectedIdRef.current === id) setHistoryFailed(true);
    }
  }, []);

  const loadMessagesInitial = useCallback(
    async (id: number, unreadHint: number) => {
      msgLoadAbortRef.current?.abort();
      const ac = new AbortController();
      msgLoadAbortRef.current = ac;
      setLoadingMessages(true);
      try {
        const resp = await whatsappApi.getMessages(
          id,
          { direction: "backward", limit: MESSAGES_PAGE },
          ac.signal
        );
        if (selectedIdRef.current !== id) return;
        messageIdsRef.current = new Set(resp.items.map((m) => m.id));
        setMessages(resp.items);
        setOlderCursor(resp.older_cursor);
        setHasOlder(resp.has_more);
        newerCursorRef.current = resp.newer_cursor;
        noteConnOk();
        const lastId = resp.items.length ? resp.items[resp.items.length - 1].id : undefined;
        maybeMarkRead(id, lastId, unreadHint);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) markConversationGone(id);
        else handleSilentError(e);
      } finally {
        if (msgLoadAbortRef.current === ac) setLoadingMessages(false);
      }
    },
    [handleSilentError, markConversationGone, maybeMarkRead, noteConnOk]
  );

  const loadOlder = useCallback(async () => {
    const id = selectedIdRef.current;
    if (!id || !olderCursor || loadingOlder) return;
    setLoadingOlder(true);
    try {
      const resp = await whatsappApi.getMessages(id, {
        direction: "backward",
        cursor: olderCursor,
        limit: MESSAGES_PAGE,
      });
      if (selectedIdRef.current !== id) return;
      const known = messageIdsRef.current;
      const added = resp.items.filter((m) => !known.has(m.id));
      added.forEach((m) => known.add(m.id));
      if (added.length > 0) {
        setMessages((prev) => [...added, ...prev].sort(compareMsg));
      }
      setOlderCursor(resp.older_cursor);
      setHasOlder(resp.has_more);
      noteConnOk();
    } catch (e) {
      handleSilentError(e);
    } finally {
      setLoadingOlder(false);
    }
  }, [olderCursor, loadingOlder, handleSilentError, noteConnOk]);

  const pollNewer = useCallback(async () => {
    const id = selectedIdRef.current;
    const cursor = newerCursorRef.current;
    if (!id || !cursor || loadingMessagesRef.current) return;
    msgPollAbortRef.current?.abort();
    const ac = new AbortController();
    msgPollAbortRef.current = ac;
    try {
      const resp = await whatsappApi.getMessages(
        id,
        { direction: "forward", cursor, limit: MESSAGES_PAGE },
        ac.signal
      );
      if (selectedIdRef.current !== id) return;
      const known = messageIdsRef.current;
      const added = resp.items.filter((m) => !known.has(m.id));
      added.forEach((m) => known.add(m.id));
      if (added.length > 0) {
        setMessages((prev) => [...prev, ...added].sort(compareMsg));
        if (resp.newer_cursor) newerCursorRef.current = resp.newer_cursor;
        const lastId = added[added.length - 1].id;
        maybeMarkRead(id, lastId, added.length);
      }
      noteConnOk();
    } catch (e) {
      handleSilentError(e);
    }
  }, [handleSilentError, maybeMarkRead, noteConnOk]);

  const selectConversation = useCallback(
    (id: number) => {
      const item = conversations.find((c) => c.conversation_id === id);
      const unreadHint = item ? item.unread_count : 0;
      setSelectedId(id);
      selectedIdRef.current = id;
      setMobilePanelOpen(true);
      setDetail(null);
      setMessages([]);
      setHistory([]);
      setHistoryFailed(false);
      setOlderCursor(null);
      setHasOlder(false);
      newerCursorRef.current = null;
      messageIdsRef.current = new Set();
      lastMarkedReadRef.current = 0;
      loadDetail(id);
      loadMessagesInitial(id, unreadHint);
      loadHistory(id);
    },
    [conversations, loadDetail, loadMessagesInitial, loadHistory]
  );

  const handleAssign = useCallback(
    async (userId: number) => {
      const id = selectedIdRef.current;
      if (!id) return;
      setAssigning(true);
      try {
        const res = await whatsappApi.assign(id, userId);
        setToast({
          msg: res.changed
            ? "Conversación asignada"
            : "La conversación ya estaba asignada a ese agente",
          kind: "ok",
        });
        loadDetail(id);
        loadHistory(id);
        fetchConversations(convLimitRef.current, { silent: true });
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          logout();
          return;
        }
        const msg =
          e instanceof ApiError ? e.message : "No se pudo asignar la conversación";
        setToast({ msg, kind: "err" });
      } finally {
        setAssigning(false);
      }
    },
    [fetchConversations, loadDetail, loadHistory, logout]
  );

  const manualRefresh = useCallback(() => {
    fetchUnread();
    fetchConversations(convLimitRef.current, { silent: true });
    if (selectedIdRef.current) pollNewer();
  }, [fetchConversations, fetchUnread, pollNewer]);

  // --- Carga inicial (una vez) ---
  useEffect(() => {
    let mounted = true;
    (async () => {
      setLoadingLines(true);
      try {
        const l = await whatsappApi.getLines();
        if (mounted) setLines(l);
      } catch (e) {
        handleSilentError(e);
      } finally {
        if (mounted) setLoadingLines(false);
      }
      if (isAdmin) {
        try {
          const u = await whatsappApi.getAssignableUsers();
          if (mounted) setAssignableUsers(u);
        } catch {
          // el selector de asignación quedará vacío; no bloquea el inbox.
        }
      }
      fetchUnread();
    })();
    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Refetch de conversaciones ante cambios de filtros (debounce) ---
  useEffect(() => {
    setConvLimit(CONV_PAGE);
    convLimitRef.current = CONV_PAGE;
    const t = setTimeout(() => {
      fetchConversations(CONV_PAGE);
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  // --- Polling ---
  useEffect(() => {
    const hidden = () => typeof document !== "undefined" && document.hidden;
    const unreadTimer = setInterval(() => {
      if (!hidden()) fetchUnread();
    }, POLL_UNREAD_MS);
    const convTimer = setInterval(() => {
      if (!hidden()) fetchConversations(convLimitRef.current, { silent: true });
    }, POLL_CONVERSATIONS_MS);
    const msgTimer = setInterval(() => {
      if (!hidden() && selectedIdRef.current) pollNewer();
    }, POLL_MESSAGES_MS);
    return () => {
      clearInterval(unreadTimer);
      clearInterval(convTimer);
      clearInterval(msgTimer);
    };
  }, [fetchUnread, fetchConversations, pollNewer]);

  // --- Reanudar al volver visible ---
  useEffect(() => {
    function onVisibility() {
      if (typeof document !== "undefined" && !document.hidden) {
        fetchUnread();
        fetchConversations(convLimitRef.current, { silent: true });
        if (selectedIdRef.current) pollNewer();
      }
    }
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [fetchUnread, fetchConversations, pollNewer]);

  // --- Limpieza de AbortControllers al desmontar ---
  useEffect(() => {
    return () => {
      convAbortRef.current?.abort();
      msgLoadAbortRef.current?.abort();
      msgPollAbortRef.current?.abort();
    };
  }, []);

  function handleLoadMore() {
    const next = Math.min(convLimit + CONV_PAGE, CONV_MAX);
    setConvLimit(next);
    convLimitRef.current = next;
    fetchConversations(next, { more: true });
  }

  function handleBack() {
    setMobilePanelOpen(false);
  }

  const hasSearch = filters.search.trim().length > 0;

  return (
    <div className="h-[calc(100vh-7rem)] min-h-[500px] flex flex-col">
      {/* Encabezado */}
      <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
        <div className="flex items-center gap-2">
          <MessageCircle className="text-green-600" size={24} />
          <h1 className="text-xl font-bold text-slate-800">WhatsApp</h1>
          {unread && unread.total_unread > 0 && (
            <UnreadBadge count={unread.total_unread} />
          )}
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-400">
          {connError ? (
            <span className="text-amber-600 flex items-center gap-1 font-medium">
              <WifiOff size={13} /> Reconectando…
            </span>
          ) : (
            lastUpdated && <span>Actualizado {formatMessageTime(lastUpdated.toISOString())}</span>
          )}
          <button
            onClick={manualRefresh}
            className="inline-flex items-center gap-1.5 text-slate-600 border border-slate-200 rounded-lg px-2.5 py-1.5 hover:bg-slate-50 font-medium"
          >
            <RefreshCw size={13} />
            Actualizar
          </button>
        </div>
      </div>

      {/* Cuerpo: dos columnas */}
      <div className="flex-1 min-h-0 flex bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
        {/* Panel izquierdo: conversaciones */}
        <div
          className={`w-full lg:w-[360px] shrink-0 flex-col border-r border-slate-200 min-h-0 ${
            mobilePanelOpen ? "hidden lg:flex" : "flex"
          }`}
        >
          {loadingLines ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="animate-spin text-slate-300" size={28} />
            </div>
          ) : lines.length === 0 ? (
            <WhatsAppEmptyState
              title="Sin líneas accesibles"
              description="No tenés líneas de WhatsApp asignadas todavía."
            />
          ) : (
            <>
              <WhatsAppFilters lines={lines} value={filters} onChange={setFilters} />
              <ConversationList
                items={conversations}
                selectedId={selectedId}
                onSelect={selectConversation}
                loading={loadingConversations}
                hasMore={hasMore}
                loadingMore={loadingMore}
                onLoadMore={handleLoadMore}
                hasSearch={hasSearch}
              />
            </>
          )}
        </div>

        {/* Panel derecho: conversación */}
        <div
          className={`flex-1 min-w-0 flex-col min-h-0 ${
            mobilePanelOpen ? "flex" : "hidden lg:flex"
          }`}
        >
          {selectedId ? (
            <ConversationPanel
              detail={detail}
              loadingDetail={loadingDetail}
              messages={messages}
              loadingMessages={loadingMessages}
              hasOlder={hasOlder}
              loadingOlder={loadingOlder}
              onLoadOlder={loadOlder}
              isAdmin={!!isAdmin}
              assignableUsers={assignableUsers}
              assigning={assigning}
              onAssign={handleAssign}
              historyItems={history}
              historyFailed={historyFailed}
              nameFor={nameFor}
              onBack={handleBack}
            />
          ) : (
            <WhatsAppEmptyState
              title="Seleccioná una conversación para ver los mensajes"
              description="Elegí una conversación del panel izquierdo."
            />
          )}
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div
          className={`fixed bottom-4 right-4 z-50 px-4 py-2.5 rounded-lg shadow-lg text-sm font-medium ${
            toast.kind === "ok" ? "bg-slate-800 text-white" : "bg-red-600 text-white"
          }`}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}
