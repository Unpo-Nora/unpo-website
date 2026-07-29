"use client";

import React from "react";
import { Search } from "lucide-react";
import { InboxBucket, InboxFilterState, LineOut } from "@/lib/whatsapp/types";

interface Props {
  lines: LineOut[];
  value: InboxFilterState;
  onChange: (next: InboxFilterState) => void;
}

const BUCKETS: { key: InboxBucket; label: string }[] = [
  { key: "all", label: "Todas" },
  { key: "mine", label: "Asignadas a mí" },
  { key: "unassigned", label: "Sin asignar" },
];

const STATUSES: { key: string; label: string }[] = [
  { key: "", label: "Todos los estados" },
  { key: "open", label: "Abiertas" },
  { key: "closed", label: "Cerradas" },
  { key: "archived", label: "Archivadas" },
];

export default function WhatsAppFilters({ lines, value, onChange }: Props) {
  function patch(part: Partial<InboxFilterState>) {
    onChange({ ...value, ...part });
  }

  return (
    <div className="p-3 border-b border-slate-200 space-y-2.5 bg-white">
      {/* Buscador */}
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          value={value.search}
          onChange={(e) => patch({ search: e.target.value })}
          placeholder="Buscar por nombre o teléfono…"
          className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
        />
      </div>

      {/* Buckets */}
      <div className="flex gap-1 bg-slate-100 rounded-lg p-0.5">
        {BUCKETS.map((b) => (
          <button
            key={b.key}
            type="button"
            onClick={() => patch({ bucket: b.key })}
            className={`flex-1 text-xs font-medium py-1.5 rounded-md transition-colors ${
              value.bucket === b.key ? "bg-white text-blue-600 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {b.label}
          </button>
        ))}
      </div>

      {/* Línea + estado + no leídas */}
      <div className="flex gap-2">
        <select
          value={value.lineId ?? ""}
          onChange={(e) => patch({ lineId: e.target.value ? Number(e.target.value) : null })}
          className="flex-1 min-w-0 text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/30"
        >
          <option value="">Todas las líneas</option>
          {lines.map((l) => (
            <option key={l.id} value={l.id}>
              {l.label}
            </option>
          ))}
        </select>
        <select
          value={value.status}
          onChange={(e) => patch({ status: e.target.value })}
          className="flex-1 min-w-0 text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/30"
        >
          {STATUSES.map((s) => (
            <option key={s.key} value={s.key}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={value.unreadOnly}
          onChange={(e) => patch({ unreadOnly: e.target.checked })}
          className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
        />
        Solo no leídas
      </label>
    </div>
  );
}
