"use client";

// Composer de texto saliente (Etapa composer, sobre el contrato 1I.1).
//
// - Enter envía; Shift+Enter inserta salto de línea.
// - Borrador SOLO en estado de React: nunca localStorage (contrato §27).
// - Guard de doble envío (además del SEND_IN_PROGRESS del backend).
// - Errores del contrato mapeados a mensajes claros; jamás detalle crudo.
// - Si el backend responde WHATSAPP_OUTBOUND_DISABLED (feature flag apagado),
//   el composer queda deshabilitado con un aviso persistente.

import React, { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Info, Loader2, Lock, SendHorizontal } from "lucide-react";
import { OUTBOUND_ERROR_CODES } from "@/lib/whatsapp/types";
import { SendResultUi } from "@/lib/whatsapp/useConversationMessages";

const MAX_TEXT = 4096;
const COUNTER_THRESHOLD = MAX_TEXT - 200;

interface Props {
  conversationId: number;
  canSend: boolean; // permiso efectivo de la línea (UX; el backend re-valida siempre)
  sending: boolean;
  onSend: (text: string) => Promise<SendResultUi>;
}

interface Notice {
  kind: "err" | "warn" | "info";
  text: string;
}

function noticeFor(result: SendResultUi): Notice | null {
  if (result.ok) {
    if (result.outcome === "failed") {
      return { kind: "warn", text: "El mensaje no se pudo enviar. Podés reintentar desde el mensaje." };
    }
    if (result.outcome === "unknown") {
      return { kind: "info", text: "Envío sin confirmación del proveedor: el estado se actualizará solo. No lo reenvíes." };
    }
    return null;
  }
  const err = result.error;
  if (!err) return { kind: "err", text: "No se pudo enviar el mensaje." };
  switch (err.code) {
    case OUTBOUND_ERROR_CODES.TEMPLATE_REQUIRED:
      return {
        kind: "warn",
        text: "La ventana de 24 h está vencida: reabrir la conversación requiere una plantilla (aún no disponible).",
      };
    case OUTBOUND_ERROR_CODES.SEND_IN_PROGRESS:
      return { kind: "info", text: "Ya hay un envío en curso en esta conversación. Esperá unos segundos." };
    case OUTBOUND_ERROR_CODES.TEXT_TOO_LONG:
      return { kind: "err", text: `El mensaje supera los ${MAX_TEXT} caracteres.` };
    case OUTBOUND_ERROR_CODES.TEXT_EMPTY:
      return { kind: "err", text: "El mensaje está vacío." };
    default:
      if (err.status === 403) return { kind: "err", text: "No tenés permiso para enviar por esta línea." };
      if (err.status === 404) return { kind: "err", text: "La conversación ya no está disponible." };
      return { kind: "err", text: err.message || "No se pudo enviar el mensaje." };
  }
}

const NOTICE_STYLES: Record<Notice["kind"], string> = {
  err: "bg-red-50 text-red-700 border-red-200",
  warn: "bg-amber-50 text-amber-700 border-amber-200",
  info: "bg-blue-50 text-blue-700 border-blue-200",
};

export default function MessageComposer({ conversationId, canSend, sending, onSend }: Props) {
  const [draft, setDraft] = useState("");
  const [notice, setNotice] = useState<Notice | null>(null);
  // El flag apagado es configuración global, no de la conversación: persiste al cambiar.
  const [outboundDisabled, setOutboundDisabled] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Cambio de conversación: borrador y avisos se descartan (nunca se persisten).
  useEffect(() => {
    setDraft("");
    setNotice(null);
  }, [conversationId]);

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, []);

  useEffect(() => {
    autoResize();
  }, [draft, autoResize]);

  const doSend = useCallback(async () => {
    if (sending || !draft.trim() || draft.length > MAX_TEXT) return;
    setNotice(null);
    const result = await onSend(draft);
    if (result.ok) {
      setDraft("");
    } else if (result.error?.code === OUTBOUND_ERROR_CODES.DISABLED) {
      setOutboundDisabled(true);
      return;
    }
    setNotice(noticeFor(result));
  }, [draft, onSend, sending]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Enter envía; Shift+Enter hace salto. `isComposing` respeta IMEs.
      if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
        e.preventDefault();
        void doSend();
      }
    },
    [doSend]
  );

  if (outboundDisabled || !canSend) {
    return (
      <div className="shrink-0 border-t border-slate-200 px-4 py-3 bg-slate-50">
        <div className="flex items-center gap-2 text-sm text-slate-400 justify-center text-center">
          <Lock size={14} className="shrink-0" />
          {outboundDisabled
            ? "El envío saliente está deshabilitado por configuración"
            : "No tenés habilitado el envío por esta línea"}
        </div>
      </div>
    );
  }

  const overLimit = draft.length > MAX_TEXT;
  const sendDisabled = sending || !draft.trim() || overLimit;

  return (
    <div className="shrink-0 border-t border-slate-200 px-3 py-2.5 bg-white">
      {notice && (
        <div
          className={`flex items-start gap-2 text-xs border rounded-lg px-3 py-2 mb-2 ${NOTICE_STYLES[notice.kind]}`}
          role="status"
        >
          {notice.kind === "info" ? (
            <Info size={14} className="shrink-0 mt-0.5" />
          ) : (
            <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          )}
          <span>{notice.text}</span>
        </div>
      )}
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          placeholder="Escribí un mensaje (Enter envía, Shift+Enter salto de línea)"
          aria-label="Mensaje"
          className="flex-1 resize-none rounded-2xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm leading-relaxed text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
        />
        <button
          type="button"
          onClick={() => void doSend()}
          disabled={sendDisabled}
          aria-label="Enviar mensaje"
          className="shrink-0 inline-flex items-center justify-center w-10 h-10 rounded-full bg-green-600 text-white hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {sending ? <Loader2 size={18} className="animate-spin" /> : <SendHorizontal size={18} />}
        </button>
      </div>
      {(draft.length > COUNTER_THRESHOLD || overLimit) && (
        <div className={`text-right text-[11px] mt-1 ${overLimit ? "text-red-600 font-semibold" : "text-slate-400"}`}>
          {draft.length}/{MAX_TEXT}
        </div>
      )}
    </div>
  );
}
