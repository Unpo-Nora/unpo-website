"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  MessageCircle,
  RefreshCw,
  Loader2,
  WifiOff,
  SlidersHorizontal,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useWhatsAppInboxData } from "@/lib/whatsapp/useWhatsAppInboxData";
import { useConversationMessages } from "@/lib/whatsapp/useConversationMessages";
import { useAssignment } from "@/lib/whatsapp/useAssignment";
import { InboxFilterState, MessageOut } from "@/lib/whatsapp/types";
import { formatMessageTime } from "@/lib/whatsapp/format";
import WhatsAppFilters from "./WhatsAppFilters";
import ConversationList from "./ConversationList";
import ConversationPanel from "./ConversationPanel";
import WhatsAppEmptyState from "./WhatsAppEmptyState";
import UnreadBadge from "./UnreadBadge";

const POLL_MESSAGES_MS = 4000;

function activeFilterCount(f: InboxFilterState): number {
  let n = 0;
  if (f.bucket !== "all") n += 1;
  if (f.lineId !== null) n += 1;
  if (f.unreadOnly) n += 1;
  if (f.status) n += 1;
  if (f.search.trim()) n += 1;
  return n;
}

export default function WhatsAppInboxDashboard() {
  const { user, logout } = useAuth();
  const isAdmin = user?.role === "admin";
  const onUnauthorized = useCallback(() => logout(), [logout]);

  const data = useWhatsAppInboxData(!!isAdmin, onUnauthorized);
  const {
    updateConversationUnread,
    removeConversation,
    noteActivity,
    refresh,
    retryInitial,
    loadMore,
  } = data;

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [toast, setToast] = useState<{ msg: string; kind: "ok" | "err" } | null>(null);
  const selectedIdRef = useRef<number | null>(null);
  const selectedHintRef = useRef(0);

  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  const handleRead = useCallback(
    (convId: number, unread: number) => {
      updateConversationUnread(convId, unread);
      refresh();
    },
    [updateConversationUnread, refresh]
  );

  const handleGone = useCallback(
    (convId: number) => {
      removeConversation(convId);
      setSelectedId(null);
      setMobilePanelOpen(false);
      setToast({ msg: "La conversación ya no está disponible", kind: "err" });
    },
    [removeConversation]
  );

  const conv = useConversationMessages({
    onUnauthorized,
    onGone: handleGone,
    onRead: handleRead,
    onConnOk: noteActivity,
  });
  const {
    select: convSelect,
    clear: convClear,
    pollNewer,
    markReadNow,
    loadOlder,
    reloadDetailAndHistory,
    sendMessage,
    retryMessage,
  } = conv;

  // Permiso de envío efectivo de la línea de la conversación abierta (UX: el backend
  // re-valida SIEMPRE; una línea incluida solo por asignación viene con can_send=false).
  const canSend = useMemo(() => {
    const lineId = conv.detail?.line.id;
    if (!lineId) return false;
    const line = data.lines.find((l) => l.id === lineId);
    return !!line && line.is_active && line.can_send;
  }, [conv.detail, data.lines]);

  const handleRetry = useCallback(
    (message: MessageOut) => {
      void retryMessage(message).then((result) => {
        if (!result.ok && result.error) {
          setToast({ msg: result.error.message, kind: "err" });
        }
      });
    },
    [retryMessage]
  );

  const onAssignDone = useCallback(
    (changed: boolean) => {
      setToast({
        msg: changed
          ? "Conversación asignada"
          : "La conversación ya estaba asignada a ese agente",
        kind: "ok",
      });
      reloadDetailAndHistory();
      refresh();
    },
    [reloadDetailAndHistory, refresh]
  );
  const onAssignError = useCallback((msg: string) => setToast({ msg, kind: "err" }), []);
  const { assigning, assign } = useAssignment(onUnauthorized, onAssignDone, onAssignError);
  const onAssign = useCallback(
    (userId: number) => {
      const id = selectedIdRef.current;
      if (id) assign(id, userId);
    },
    [assign]
  );

  // Selección -> cargar / limpiar mensajes de la conversación.
  useEffect(() => {
    if (selectedId === null) convClear();
    else convSelect(selectedId, selectedHintRef.current);
  }, [selectedId, convSelect, convClear]);

  // Polling de mensajes nuevos de la conversación abierta (pausado con pestaña oculta).
  useEffect(() => {
    const hidden = () => typeof document !== "undefined" && document.hidden;
    const t = setInterval(() => {
      if (!hidden() && selectedIdRef.current) pollNewer();
    }, POLL_MESSAGES_MS);
    return () => clearInterval(t);
  }, [pollNewer]);

  // Al volver visible: refrescar y, si hay conversación, traer nuevos + marcar leídos ya
  // cargados (aunque no haya llegado ningún mensaje nuevo).
  useEffect(() => {
    function onVisibility() {
      if (typeof document !== "undefined" && !document.hidden) {
        refresh();
        if (selectedIdRef.current) {
          pollNewer();
          markReadNow();
        }
      }
    }
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [refresh, pollNewer, markReadNow]);

  const selectConversation = useCallback(
    (id: number) => {
      const item = data.conversations.find((c) => c.conversation_id === id);
      selectedHintRef.current = item ? item.unread_count : 0;
      setSelectedId(id);
      setMobilePanelOpen(true);
    },
    [data.conversations]
  );

  const manualRefresh = useCallback(() => {
    retryInitial();
    if (selectedIdRef.current) {
      pollNewer();
      markReadNow();
    }
  }, [retryInitial, pollNewer, markReadNow]);

  const activeFilters = activeFilterCount(data.filters);
  const hasSearch = data.filters.search.trim().length > 0;

  function renderLeftContent() {
    if (data.loadingLines && data.lines.length === 0) {
      return (
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="animate-spin text-slate-300" size={28} />
        </div>
      );
    }
    if (data.lines.length === 0 && data.linesError) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-6 gap-3">
          <WifiOff size={36} className="text-amber-500" />
          <p className="text-slate-600 font-medium">No se pudieron cargar las líneas</p>
          <p className="text-sm text-slate-400">Revisá la conexión e intentá de nuevo.</p>
          <button
            onClick={manualRefresh}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 border border-blue-200 rounded-lg px-3 py-1.5 hover:bg-blue-50"
          >
            <RefreshCw size={14} /> Reintentar
          </button>
        </div>
      );
    }
    if (data.lines.length === 0) {
      return (
        <WhatsAppEmptyState
          title="Sin líneas accesibles"
          description="No tenés líneas de WhatsApp asignadas todavía."
        />
      );
    }
    return (
      <>
        <button
          type="button"
          onClick={() => setMobileFiltersOpen((v) => !v)}
          className="lg:hidden flex items-center justify-between gap-2 px-3 py-2.5 border-b border-slate-200 text-sm font-medium text-slate-600"
        >
          <span className="inline-flex items-center gap-2">
            <SlidersHorizontal size={16} /> Filtros
            {activeFilters > 0 && (
              <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-blue-600 text-white text-[10px] font-bold">
                {activeFilters}
              </span>
            )}
          </span>
          <span className="text-xs text-slate-400">{mobileFiltersOpen ? "Ocultar" : "Mostrar"}</span>
        </button>
        <div className={`${mobileFiltersOpen ? "block" : "hidden"} lg:block`}>
          <WhatsAppFilters lines={data.lines} value={data.filters} onChange={data.setFilters} />
        </div>
        <ConversationList
          items={data.conversations}
          selectedId={selectedId}
          onSelect={selectConversation}
          loading={data.loadingConversations}
          hasMore={data.hasMore}
          loadingMore={data.loadingMore}
          onLoadMore={loadMore}
          hasSearch={hasSearch}
        />
      </>
    );
  }

  return (
    <div className="h-[calc(100vh-7rem)] min-h-[500px] flex flex-col">
      {/* Encabezado */}
      <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
        <div className="flex items-center gap-2">
          <MessageCircle className="text-green-600" size={24} />
          <h1 className="text-xl font-bold text-slate-800">WhatsApp</h1>
          {data.unread && data.unread.total_unread > 0 && (
            <UnreadBadge count={data.unread.total_unread} />
          )}
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-400">
          {data.connError ? (
            <span className="text-amber-600 flex items-center gap-1 font-medium">
              <WifiOff size={13} /> Reconectando…
            </span>
          ) : (
            data.lastUpdated && (
              <span>Actualizado {formatMessageTime(data.lastUpdated.toISOString())}</span>
            )
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
        <div
          className={`w-full lg:w-[360px] shrink-0 flex-col border-r border-slate-200 min-h-0 ${
            mobilePanelOpen ? "hidden lg:flex" : "flex"
          }`}
        >
          {renderLeftContent()}
        </div>

        <div
          className={`flex-1 min-w-0 flex-col min-h-0 ${
            mobilePanelOpen ? "flex" : "hidden lg:flex"
          }`}
        >
          {selectedId ? (
            <ConversationPanel
              detail={conv.detail}
              loadingDetail={conv.loadingDetail}
              messages={conv.messages}
              loadingMessages={conv.loadingMessages}
              hasOlder={conv.hasOlder}
              loadingOlder={conv.loadingOlder}
              onLoadOlder={loadOlder}
              isAdmin={!!isAdmin}
              assignableUsers={data.assignableUsers}
              assigning={assigning}
              onAssign={onAssign}
              historyItems={conv.history}
              historyFailed={conv.historyFailed}
              nameFor={data.nameFor}
              onBack={() => setMobilePanelOpen(false)}
              canSend={canSend}
              sending={conv.sending}
              onSend={sendMessage}
              onRetry={handleRetry}
            />
          ) : (
            <WhatsAppEmptyState
              title="Seleccioná una conversación para ver los mensajes"
              description="Elegí una conversación del panel izquierdo."
            />
          )}
        </div>
      </div>

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
