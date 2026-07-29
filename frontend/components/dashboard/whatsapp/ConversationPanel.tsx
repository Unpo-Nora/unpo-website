"use client";

import React from "react";
import { ArrowLeft, Lock, Phone } from "lucide-react";
import {
  AssignableUser,
  AssignmentHistoryOut,
  ConversationDetail,
  MessageOut,
} from "@/lib/whatsapp/types";
import { contactLabel, conversationStatusLabel } from "@/lib/whatsapp/format";
import MessageTimeline from "./MessageTimeline";
import AssignmentControl from "./AssignmentControl";
import AssignmentHistory from "./AssignmentHistory";
import WhatsAppEmptyState from "./WhatsAppEmptyState";

interface Props {
  detail: ConversationDetail | null;
  loadingDetail: boolean;
  messages: MessageOut[];
  loadingMessages: boolean;
  hasOlder: boolean;
  loadingOlder: boolean;
  onLoadOlder: () => void;
  isAdmin: boolean;
  assignableUsers: AssignableUser[];
  assigning: boolean;
  onAssign: (userId: number) => void;
  historyItems: AssignmentHistoryOut[];
  historyFailed: boolean;
  nameFor: (id: number | null) => string;
  onBack: () => void;
}

const STATUS_STYLES: Record<string, string> = {
  open: "bg-green-100 text-green-700",
  closed: "bg-slate-200 text-slate-600",
  archived: "bg-amber-100 text-amber-700",
};

export default function ConversationPanel({
  detail,
  loadingDetail,
  messages,
  loadingMessages,
  hasOlder,
  loadingOlder,
  onLoadOlder,
  isAdmin,
  assignableUsers,
  assigning,
  onAssign,
  historyItems,
  historyFailed,
  nameFor,
  onBack,
}: Props) {
  if (!detail && !loadingDetail) {
    return (
      <WhatsAppEmptyState
        title="Seleccioná una conversación para ver los mensajes"
        description="Elegí una conversación del panel izquierdo."
      />
    );
  }

  return (
    <div className="flex flex-col h-full min-h-0 bg-white">
      {/* Header */}
      <div className="shrink-0 border-b border-slate-200 px-4 py-3">
        <div className="flex items-start gap-3">
          <button
            onClick={onBack}
            className="lg:hidden p-1 -ml-1 text-slate-500 hover:bg-slate-100 rounded shrink-0"
            aria-label="Volver a la lista"
          >
            <ArrowLeft size={20} />
          </button>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="font-bold text-slate-800 truncate">
                {detail ? contactLabel(detail.contact) : "Cargando…"}
              </h2>
              {detail && (
                <span
                  className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                    STATUS_STYLES[detail.status] ?? "bg-slate-100 text-slate-600"
                  }`}
                >
                  {conversationStatusLabel(detail.status)}
                </span>
              )}
            </div>
            {detail && (
              <div className="flex items-center gap-3 mt-0.5 text-xs text-slate-500 flex-wrap">
                {detail.contact.phone_masked && (
                  <span className="inline-flex items-center gap-1">
                    <Phone size={12} />
                    {detail.contact.phone_masked}
                  </span>
                )}
                <span className="inline-flex items-center gap-1">Línea: {detail.line.label}</span>
              </div>
            )}
          </div>
        </div>
        {detail && (
          <div className="mt-2.5">
            <AssignmentControl
              conversationId={detail.conversation_id}
              isAdmin={isAdmin}
              currentAssigned={detail.assigned_user}
              assignableUsers={assignableUsers}
              assigning={assigning}
              onAssign={onAssign}
            />
          </div>
        )}
      </div>

      {/* Timeline */}
      {detail && (
        <MessageTimeline
          conversationId={detail.conversation_id}
          messages={messages}
          loadingInitial={loadingMessages && messages.length === 0}
          hasOlder={hasOlder}
          loadingOlder={loadingOlder}
          onLoadOlder={onLoadOlder}
        />
      )}

      {/* Historial de asignaciones */}
      {detail && <AssignmentHistory items={historyItems} failed={historyFailed} nameFor={nameFor} />}

      {/* Pie informativo (envío deshabilitado en esta etapa) */}
      <div className="shrink-0 border-t border-slate-200 px-4 py-3 bg-slate-50">
        <div className="flex items-center gap-2 text-sm text-slate-400 justify-center">
          <Lock size={14} />
          El envío de mensajes se habilitará en una próxima etapa
        </div>
      </div>
    </div>
  );
}
