"use client";

// Mensajes de la conversación seleccionada: detalle, timeline con cursores older/newer,
// polling forward (incluida conversación inicialmente vacía) y marcado de lectura
// coordinado (usa el unread REAL, respeta document.hidden, no repite ni superpone).

import { useCallback, useEffect, useRef, useState } from "react";
import { whatsappApi } from "./api";
import {
  ApiError,
  AssignmentHistoryOut,
  ConversationDetail,
  MessageOut,
} from "./types";

const MESSAGES_PAGE = 50;

function compareMsg(a: MessageOut, b: MessageOut): number {
  const ca = a.created_at ?? "";
  const cb = b.created_at ?? "";
  if (ca < cb) return -1;
  if (ca > cb) return 1;
  return a.id - b.id;
}

function isAbort(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

export interface ConversationMessages {
  detail: ConversationDetail | null;
  loadingDetail: boolean;
  messages: MessageOut[];
  loadingMessages: boolean;
  hasOlder: boolean;
  loadingOlder: boolean;
  loadOlder: () => void;
  history: AssignmentHistoryOut[];
  historyFailed: boolean;
  pollNewer: () => void;
  markReadNow: () => void;
  select: (id: number, unreadHint: number) => void;
  clear: () => void;
  reloadDetailAndHistory: () => void;
}

interface Options {
  onUnauthorized: () => void;
  onGone: (convId: number) => void;
  onRead: (convId: number, unread: number) => void;
  onConnOk: () => void;
}

export function useConversationMessages(opts: Options): ConversationMessages {
  const { onUnauthorized, onGone, onRead, onConnOk } = opts;

  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [hasOlder, setHasOlder] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [olderCursor, setOlderCursor] = useState<string | null>(null);
  const [history, setHistory] = useState<AssignmentHistoryOut[]>([]);
  const [historyFailed, setHistoryFailed] = useState(false);

  const selectedIdRef = useRef<number | null>(null);
  const newerCursorRef = useRef<string | null>(null);
  const messageIdsRef = useRef<Set<number>>(new Set());
  const lastLoadedMsgIdRef = useRef(0);
  const lastMarkedReadRef = useRef(0);
  const currentUnreadRef = useRef(0);
  const markInFlightRef = useRef(false);
  const loadingMessagesRef = useRef(false);
  const olderCursorRef = useRef<string | null>(null);
  const loadingOlderRef = useRef(false);

  const detailAbortRef = useRef<AbortController | null>(null);
  const historyAbortRef = useRef<AbortController | null>(null);
  const msgLoadAbortRef = useRef<AbortController | null>(null);
  const olderAbortRef = useRef<AbortController | null>(null);
  const pollAbortRef = useRef<AbortController | null>(null);
  const pollInFlightRef = useRef(false);

  useEffect(() => {
    loadingMessagesRef.current = loadingMessages;
  }, [loadingMessages]);
  useEffect(() => {
    olderCursorRef.current = olderCursor;
  }, [olderCursor]);
  useEffect(() => {
    loadingOlderRef.current = loadingOlder;
  }, [loadingOlder]);

  const handleSilent = useCallback(
    (e: unknown) => {
      if (isAbort(e)) return;
      if (e instanceof ApiError && e.status === 401) onUnauthorized();
    },
    [onUnauthorized]
  );

  const maybeMarkRead = useCallback(() => {
    const id = selectedIdRef.current;
    if (!id) return;
    if (typeof document !== "undefined" && document.hidden) return;
    if (loadingMessagesRef.current) return;
    if (lastLoadedMsgIdRef.current <= 0) return;
    if (currentUnreadRef.current <= 0) return;
    if (lastLoadedMsgIdRef.current <= lastMarkedReadRef.current) return;
    if (markInFlightRef.current) return;
    const targetId = lastLoadedMsgIdRef.current;
    markInFlightRef.current = true;
    const prevMarked = lastMarkedReadRef.current;
    lastMarkedReadRef.current = targetId; // optimista para no superponer
    whatsappApi
      .markRead(id, targetId)
      .then((res) => {
        currentUnreadRef.current = res.unread_count;
        setDetail((d) =>
          d && d.conversation_id === id ? { ...d, unread_count: res.unread_count } : d
        );
        onRead(id, res.unread_count);
      })
      .catch((e) => {
        lastMarkedReadRef.current = prevMarked; // permitir reintento
        if (e instanceof ApiError && e.status === 401) onUnauthorized();
      })
      .finally(() => {
        markInFlightRef.current = false;
      });
  }, [onRead, onUnauthorized]);

  const loadDetail = useCallback(
    async (id: number) => {
      detailAbortRef.current?.abort();
      const ac = new AbortController();
      detailAbortRef.current = ac;
      setLoadingDetail(true);
      try {
        const d = await whatsappApi.getConversation(id, ac.signal);
        if (selectedIdRef.current !== id) return;
        setDetail(d);
        currentUnreadRef.current = d.unread_count; // unread REAL (autoridad)
        onConnOk();
        maybeMarkRead();
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) onGone(id);
        else handleSilent(e);
      } finally {
        if (detailAbortRef.current === ac) setLoadingDetail(false);
      }
    },
    [handleSilent, maybeMarkRead, onConnOk, onGone]
  );

  const loadHistory = useCallback(
    async (id: number) => {
      historyAbortRef.current?.abort();
      const ac = new AbortController();
      historyAbortRef.current = ac;
      try {
        const h = await whatsappApi.getAssignments(id, ac.signal);
        if (selectedIdRef.current !== id) return;
        setHistory(h.items);
        setHistoryFailed(false);
      } catch (e) {
        if (isAbort(e)) return;
        if (e instanceof ApiError && e.status === 401) {
          onUnauthorized();
          return;
        }
        if (selectedIdRef.current === id) setHistoryFailed(true);
      }
    },
    [onUnauthorized]
  );

  const loadMessagesInitial = useCallback(
    async (id: number) => {
      msgLoadAbortRef.current?.abort();
      const ac = new AbortController();
      msgLoadAbortRef.current = ac;
      setLoadingMessages(true);
      loadingMessagesRef.current = true;
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
        lastLoadedMsgIdRef.current = resp.items.length
          ? resp.items[resp.items.length - 1].id
          : 0;
        onConnOk();
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) onGone(id);
        else handleSilent(e);
      } finally {
        if (msgLoadAbortRef.current === ac) {
          setLoadingMessages(false);
          loadingMessagesRef.current = false;
          maybeMarkRead();
        }
      }
    },
    [handleSilent, maybeMarkRead, onConnOk, onGone]
  );

  const loadOlder = useCallback(async () => {
    const id = selectedIdRef.current;
    const cursor = olderCursorRef.current;
    if (!id || !cursor || loadingOlderRef.current) return;
    olderAbortRef.current?.abort();
    const ac = new AbortController();
    olderAbortRef.current = ac;
    setLoadingOlder(true);
    try {
      const resp = await whatsappApi.getMessages(
        id,
        { direction: "backward", cursor, limit: MESSAGES_PAGE },
        ac.signal
      );
      if (selectedIdRef.current !== id) return;
      const known = messageIdsRef.current;
      const added = resp.items.filter((m) => !known.has(m.id));
      added.forEach((m) => known.add(m.id));
      if (added.length > 0) {
        setMessages((prev) => [...added, ...prev].sort(compareMsg));
      }
      setOlderCursor(resp.older_cursor);
      setHasOlder(resp.has_more);
      onConnOk();
    } catch (e) {
      handleSilent(e);
    } finally {
      if (olderAbortRef.current === ac) setLoadingOlder(false);
    }
  }, [handleSilent, onConnOk]);

  const pollNewer = useCallback(async () => {
    const id = selectedIdRef.current;
    if (!id || loadingMessagesRef.current || pollInFlightRef.current) return;
    pollInFlightRef.current = true;
    pollAbortRef.current?.abort();
    const ac = new AbortController();
    pollAbortRef.current = ac;
    try {
      const cursor = newerCursorRef.current;
      // Conversación vacía: forward SIN cursor detecta el primer mensaje; con cursor,
      // solo mensajes posteriores (no re-descarga histórico).
      const resp = await whatsappApi.getMessages(
        id,
        cursor
          ? { direction: "forward", cursor, limit: MESSAGES_PAGE }
          : { direction: "forward", limit: MESSAGES_PAGE },
        ac.signal
      );
      if (selectedIdRef.current !== id) return;
      const known = messageIdsRef.current;
      const added = resp.items.filter((m) => !known.has(m.id));
      added.forEach((m) => known.add(m.id));
      if (added.length > 0) {
        setMessages((prev) => [...prev, ...added].sort(compareMsg));
        if (resp.newer_cursor) newerCursorRef.current = resp.newer_cursor;
        const maxId = Math.max(...added.map((m) => m.id));
        if (maxId > lastLoadedMsgIdRef.current) lastLoadedMsgIdRef.current = maxId;
        const inbound = added.filter((m) => m.direction === "inbound").length;
        if (inbound > 0) currentUnreadRef.current += inbound;
        maybeMarkRead();
      }
      onConnOk();
    } catch (e) {
      handleSilent(e);
    } finally {
      pollInFlightRef.current = false;
    }
  }, [handleSilent, maybeMarkRead, onConnOk]);

  const resetSelection = useCallback(() => {
    setDetail(null);
    setMessages([]);
    setHistory([]);
    setHistoryFailed(false);
    setOlderCursor(null);
    setHasOlder(false);
    olderCursorRef.current = null;
    newerCursorRef.current = null;
    messageIdsRef.current = new Set();
    lastLoadedMsgIdRef.current = 0;
    lastMarkedReadRef.current = 0;
    currentUnreadRef.current = 0;
  }, []);

  const select = useCallback(
    (id: number, unreadHint: number) => {
      // cancelar requests de la conversación anterior
      detailAbortRef.current?.abort();
      historyAbortRef.current?.abort();
      msgLoadAbortRef.current?.abort();
      olderAbortRef.current?.abort();
      pollAbortRef.current?.abort();
      selectedIdRef.current = id;
      resetSelection();
      currentUnreadRef.current = unreadHint;
      loadDetail(id);
      loadMessagesInitial(id);
      loadHistory(id);
    },
    [loadDetail, loadHistory, loadMessagesInitial, resetSelection]
  );

  const clear = useCallback(() => {
    selectedIdRef.current = null;
    detailAbortRef.current?.abort();
    historyAbortRef.current?.abort();
    msgLoadAbortRef.current?.abort();
    olderAbortRef.current?.abort();
    pollAbortRef.current?.abort();
    resetSelection();
  }, [resetSelection]);

  const reloadDetailAndHistory = useCallback(() => {
    const id = selectedIdRef.current;
    if (id) {
      loadDetail(id);
      loadHistory(id);
    }
  }, [loadDetail, loadHistory]);

  const markReadNow = useCallback(() => {
    maybeMarkRead();
  }, [maybeMarkRead]);

  useEffect(() => {
    return () => {
      detailAbortRef.current?.abort();
      historyAbortRef.current?.abort();
      msgLoadAbortRef.current?.abort();
      olderAbortRef.current?.abort();
      pollAbortRef.current?.abort();
    };
  }, []);

  return {
    detail,
    loadingDetail,
    messages,
    loadingMessages,
    hasOlder,
    loadingOlder,
    loadOlder,
    history,
    historyFailed,
    pollNewer,
    markReadNow,
    select,
    clear,
    reloadDetailAndHistory,
  };
}
