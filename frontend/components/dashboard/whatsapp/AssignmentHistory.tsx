"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight, History } from "lucide-react";
import { AssignmentHistoryOut } from "@/lib/whatsapp/types";
import { formatFullDateTime } from "@/lib/whatsapp/format";

interface Props {
  items: AssignmentHistoryOut[];
  failed: boolean;
  // Resuelve un id de usuario a su nombre (o "Usuario #<id>" si no se puede resolver).
  nameFor: (id: number | null) => string;
}

export default function AssignmentHistory({ items, failed, nameFor }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-t border-slate-200">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
      >
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        <History size={15} />
        Historial de asignaciones
        {items.length > 0 && <span className="text-xs text-slate-400">({items.length})</span>}
      </button>
      {open && (
        <div className="px-4 pb-3 max-h-48 overflow-y-auto">
          {failed ? (
            <p className="text-xs text-slate-400 py-2">
              No se pudo cargar el historial en este momento.
            </p>
          ) : items.length === 0 ? (
            <p className="text-xs text-slate-400 py-2">Sin cambios de asignación registrados.</p>
          ) : (
            <ul className="space-y-2">
              {items.map((h) => (
                <li key={h.id} className="text-xs text-slate-600 border-l-2 border-slate-200 pl-2">
                  <div>
                    <span className="text-slate-400">De</span>{" "}
                    <span className="font-medium">
                      {h.from_user_id ? nameFor(h.from_user_id) : "Sin asignar"}
                    </span>{" "}
                    <span className="text-slate-400">a</span>{" "}
                    <span className="font-medium">{nameFor(h.to_user_id)}</span>
                  </div>
                  <div className="text-slate-400">
                    {h.assigned_by_user_id && (
                      <span>Por {nameFor(h.assigned_by_user_id)} · </span>
                    )}
                    {formatFullDateTime(h.created_at)}
                  </div>
                  {h.reason && <div className="text-slate-500 italic">“{h.reason}”</div>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
