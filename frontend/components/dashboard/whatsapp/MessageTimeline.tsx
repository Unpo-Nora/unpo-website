"use client";

import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Loader2, ArrowDown, ChevronUp } from "lucide-react";
import { MessageOut } from "@/lib/whatsapp/types";
import MessageBubble from "./MessageBubble";
import WhatsAppEmptyState from "./WhatsAppEmptyState";

interface Props {
  conversationId: number;
  messages: MessageOut[];
  loadingInitial: boolean;
  hasOlder: boolean;
  loadingOlder: boolean;
  onLoadOlder: () => void;
  onRetry?: (message: MessageOut) => void;
}

export default function MessageTimeline({
  conversationId,
  messages,
  loadingInitial,
  hasOlder,
  loadingOlder,
  onLoadOlder,
  onRetry,
}: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const prev = useRef<{ firstId: number | null; lastId: number | null; height: number; top: number }>({
    firstId: null,
    lastId: null,
    height: 0,
    top: 0,
  });
  const initialDone = useRef(false);
  const [atBottom, setAtBottom] = useState(true);
  const [newCount, setNewCount] = useState(0);

  // Reset al cambiar de conversación.
  useEffect(() => {
    initialDone.current = false;
    prev.current = { firstId: null, lastId: null, height: 0, top: 0 };
    setAtBottom(true);
    setNewCount(0);
  }, [conversationId]);

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el || messages.length === 0) return;
    const firstId = messages[0].id;
    const lastId = messages[messages.length - 1].id;
    const p = prev.current;
    const isPrepend =
      p.firstId !== null && firstId !== p.firstId && messages.some((m) => m.id === p.firstId);
    const isAppend = p.lastId !== null && lastId !== p.lastId && !isPrepend;

    if (!initialDone.current) {
      // Primer render de la conversación -> scroll inicial al final.
      el.scrollTop = el.scrollHeight;
      initialDone.current = true;
      setNewCount(0);
    } else if (isPrepend) {
      // Se antepusieron mensajes más antiguos -> preservar la posición de lectura.
      el.scrollTop = el.scrollHeight - p.height + p.top;
    } else if (isAppend) {
      if (atBottom) {
        el.scrollTop = el.scrollHeight;
        setNewCount(0);
      } else {
        const idx = messages.findIndex((m) => m.id === p.lastId);
        const added = idx >= 0 ? messages.length - 1 - idx : 0;
        if (added > 0) setNewCount((c) => c + added);
      }
    }
    prev.current = { firstId, lastId, height: el.scrollHeight, top: el.scrollTop };
  }, [messages, atBottom]);

  function handleScroll() {
    const el = scrollRef.current;
    if (!el) return;
    const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const nowAtBottom = distanceToBottom < 80;
    setAtBottom(nowAtBottom);
    if (nowAtBottom) setNewCount(0);
  }

  function scrollToBottom() {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
    setAtBottom(true);
    setNewCount(0);
  }

  if (loadingInitial) {
    return (
      <div className="flex-1 flex flex-col gap-3 p-4 bg-slate-50 overflow-hidden">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className={`flex ${i % 2 ? "justify-end" : "justify-start"}`}>
            <div className="h-10 w-40 rounded-2xl bg-slate-200 animate-pulse" />
          </div>
        ))}
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <WhatsAppEmptyState
        title="No hay mensajes en esta conversación"
        description="Cuando el contacto escriba, sus mensajes van a aparecer acá."
      />
    );
  }

  return (
    <div className="relative flex-1 min-h-0">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto px-4 py-4 space-y-2 bg-slate-50"
      >
        {hasOlder && (
          <div className="flex justify-center pb-2">
            <button
              onClick={onLoadOlder}
              disabled={loadingOlder}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 bg-white border border-slate-200 rounded-full px-3 py-1.5 hover:bg-blue-50 disabled:opacity-60"
            >
              {loadingOlder ? <Loader2 className="animate-spin" size={14} /> : <ChevronUp size={14} />}
              Cargar mensajes anteriores
            </button>
          </div>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} onRetry={onRetry} />
        ))}
      </div>
      {newCount > 0 && !atBottom && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-4 left-1/2 -translate-x-1/2 inline-flex items-center gap-1.5 text-xs font-bold text-white bg-blue-600 rounded-full px-3 py-1.5 shadow-lg hover:bg-blue-700"
        >
          <ArrowDown size={14} />
          {newCount} mensaje{newCount > 1 ? "s" : ""} nuevo{newCount > 1 ? "s" : ""}
        </button>
      )}
    </div>
  );
}
