"use client";

import React from "react";
import { UserCircle } from "lucide-react";
import { ConversationListItem as ConversationItem } from "@/lib/whatsapp/types";
import {
  contactLabel,
  formatConversationTime,
  messageTypeLabel,
  userDisplayName,
} from "@/lib/whatsapp/format";
import UnreadBadge from "./UnreadBadge";

interface Props {
  item: ConversationItem;
  selected: boolean;
  onSelect: (id: number) => void;
}

export default function ConversationListItem({ item, selected, onSelect }: Props) {
  const preview =
    item.last_message_type && item.last_message_type !== "text"
      ? `[${messageTypeLabel(item.last_message_type)}]`
      : item.last_message_preview || "Sin mensajes";
  const prefix = item.last_message_direction === "outbound" ? "Vos: " : "";

  return (
    <button
      type="button"
      onClick={() => onSelect(item.conversation_id)}
      className={`w-full text-left px-3 py-3 border-b border-slate-100 transition-colors ${
        selected ? "bg-blue-50" : "hover:bg-slate-50"
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="shrink-0 mt-0.5 text-slate-300">
          <UserCircle size={38} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold text-slate-800 truncate">
              {contactLabel(item.contact)}
            </span>
            <span className="shrink-0 text-[11px] text-slate-400">
              {formatConversationTime(item.last_message_at)}
            </span>
          </div>
          <div className="flex items-center justify-between gap-2 mt-0.5">
            <p className="text-sm text-slate-500 truncate">
              {prefix}
              {preview}
            </p>
            <UnreadBadge count={item.unread_count} className="shrink-0" />
          </div>
          <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
            <span className="text-[10px] font-medium text-slate-500 bg-slate-100 rounded px-1.5 py-0.5 truncate max-w-[45%]">
              {item.line.label}
            </span>
            {item.assigned_user ? (
              <span className="text-[10px] font-medium text-blue-600 bg-blue-50 rounded px-1.5 py-0.5 truncate max-w-[45%]">
                {userDisplayName(item.assigned_user.full_name, item.assigned_user.id)}
              </span>
            ) : (
              <span className="text-[10px] font-medium text-amber-700 bg-amber-50 rounded px-1.5 py-0.5">
                Sin asignar
              </span>
            )}
          </div>
        </div>
      </div>
    </button>
  );
}
