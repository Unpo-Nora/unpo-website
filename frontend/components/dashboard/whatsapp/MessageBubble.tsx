"use client";

import React from "react";
import {
  Check,
  CheckCheck,
  Clock,
  AlertTriangle,
  HelpCircle,
  Loader2,
  Paperclip,
  RotateCcw,
} from "lucide-react";
import { MessageOut } from "@/lib/whatsapp/types";
import { formatMessageTime, messageTypeLabel } from "@/lib/whatsapp/format";

const OUTBOUND_STATUS: Record<string, { label: string; icon: React.ReactNode }> = {
  pending: { label: "Pendiente", icon: <Clock size={13} /> },
  sending: { label: "Enviando", icon: <Loader2 size={13} className="animate-spin" /> },
  accepted: { label: "Aceptado", icon: <Clock size={13} /> },
  sent: { label: "Enviado", icon: <Check size={13} /> },
  delivered: { label: "Entregado", icon: <CheckCheck size={13} /> },
  read: { label: "Leído", icon: <CheckCheck size={13} className="text-blue-500" /> },
  failed: { label: "Falló", icon: <AlertTriangle size={13} className="text-red-300" /> },
  // `unknown` NUNCA ofrece reintento: podría duplicar un envío que en realidad salió.
  unknown: { label: "Sin confirmación", icon: <HelpCircle size={13} /> },
};

interface Props {
  message: MessageOut;
  onRetry?: (message: MessageOut) => void;
}

export default function MessageBubble({ message, onRetry }: Props) {
  const isOutbound = message.direction === "outbound";
  const isText = message.message_type === "text";
  const status = isOutbound ? OUTBOUND_STATUS[message.current_status] : undefined;
  const canRetry = isOutbound && message.current_status === "failed" && !!onRetry;

  return (
    <div className={`flex ${isOutbound ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[78%] sm:max-w-[70%] rounded-2xl px-3.5 py-2 shadow-sm ${
          isOutbound
            ? "bg-green-600 text-white rounded-br-sm"
            : "bg-white text-slate-800 border border-slate-200 rounded-bl-sm"
        }`}
      >
        {!isText && (
          <span
            className={`inline-flex items-center gap-1 text-xs font-medium mb-1 ${
              isOutbound ? "text-green-50" : "text-slate-500"
            }`}
          >
            <Paperclip size={12} />
            {messageTypeLabel(message.message_type)}
          </span>
        )}
        {/* Texto renderizado como TEXTO (nunca dangerouslySetInnerHTML). */}
        {message.text_body ? (
          <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">
            {message.text_body}
          </p>
        ) : (
          !isText && (
            <p className={`text-sm italic ${isOutbound ? "text-green-50" : "text-slate-400"}`}>
              (contenido no soportado)
            </p>
          )
        )}
        <div
          className={`flex items-center gap-1 justify-end mt-0.5 text-[11px] ${
            isOutbound ? "text-green-100" : "text-slate-400"
          }`}
        >
          <span>{formatMessageTime(message.created_at)}</span>
          {status && (
            <span className="inline-flex items-center gap-0.5" title={status.label}>
              {status.icon}
            </span>
          )}
        </div>
        {canRetry && (
          <div className="flex justify-end mt-1">
            <button
              type="button"
              onClick={() => onRetry!(message)}
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-green-50 underline decoration-green-200/70 hover:text-white"
            >
              <RotateCcw size={11} />
              Reintentar
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
