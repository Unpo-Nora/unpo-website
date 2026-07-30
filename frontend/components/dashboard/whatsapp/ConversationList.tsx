"use client";

import React from "react";
import { Loader2, Inbox, SearchX } from "lucide-react";
import { ConversationListItem as ConversationItem } from "@/lib/whatsapp/types";
import ConversationListItem from "./ConversationListItem";
import WhatsAppEmptyState from "./WhatsAppEmptyState";

interface Props {
  items: ConversationItem[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  loading: boolean;
  hasMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
  hasSearch: boolean;
}

export default function ConversationList({
  items,
  selectedId,
  onSelect,
  loading,
  hasMore,
  loadingMore,
  onLoadMore,
  hasSearch,
}: Props) {
  if (loading && items.length === 0) {
    return (
      <div className="flex-1 overflow-y-auto">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="px-3 py-3 border-b border-slate-100 flex gap-3">
            <div className="w-10 h-10 rounded-full bg-slate-200 animate-pulse shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-3 w-1/2 bg-slate-200 rounded animate-pulse" />
              <div className="h-3 w-3/4 bg-slate-100 rounded animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return hasSearch ? (
      <WhatsAppEmptyState
        title="Sin resultados"
        description="No hay conversaciones que coincidan con la búsqueda."
        icon={<SearchX size={40} />}
      />
    ) : (
      <WhatsAppEmptyState
        title="No hay conversaciones"
        description="Todavía no hay conversaciones en tu bandeja."
        icon={<Inbox size={40} />}
      />
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {items.map((item) => (
        <ConversationListItem
          key={item.conversation_id}
          item={item}
          selected={item.conversation_id === selectedId}
          onSelect={onSelect}
        />
      ))}
      {hasMore && (
        <div className="p-3 flex justify-center">
          <button
            onClick={onLoadMore}
            disabled={loadingMore}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-700 disabled:opacity-60"
          >
            {loadingMore && <Loader2 className="animate-spin" size={14} />}
            Cargar más
          </button>
        </div>
      )}
    </div>
  );
}
