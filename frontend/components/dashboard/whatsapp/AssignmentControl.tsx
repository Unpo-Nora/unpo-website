"use client";

import React, { useEffect, useState } from "react";
import { Loader2, UserCheck } from "lucide-react";
import { AssignableUser, AssignedUserOut } from "@/lib/whatsapp/types";
import { userDisplayName } from "@/lib/whatsapp/format";

interface Props {
  conversationId: number;
  isAdmin: boolean;
  currentAssigned: AssignedUserOut | null;
  assignableUsers: AssignableUser[];
  assigning: boolean;
  onAssign: (userId: number) => void;
}

export default function AssignmentControl({
  conversationId,
  isAdmin,
  currentAssigned,
  assignableUsers,
  assigning,
  onAssign,
}: Props) {
  const [selected, setSelected] = useState<string>("");
  const [confirming, setConfirming] = useState(false);

  // No arrastrar el agente elegido/confirmación entre conversaciones ni tras reasignar.
  const currentAssignedId = currentAssigned?.id ?? null;
  useEffect(() => {
    setSelected("");
    setConfirming(false);
  }, [conversationId, currentAssignedId]);

  const isReassign = currentAssigned != null;

  // Vendedor: solo lectura de la asignación actual.
  if (!isAdmin) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <span className="text-slate-500">Asignada a:</span>
        <span className="font-medium text-slate-700">
          {currentAssigned
            ? userDisplayName(currentAssigned.full_name, currentAssigned.id)
            : "Sin asignar"}
        </span>
      </div>
    );
  }

  const selectedUser = assignableUsers.find((u) => String(u.id) === selected);

  function handlePrimary() {
    if (selected === "") return;
    if (isReassign && !confirming) {
      setConfirming(true);
      return;
    }
    onAssign(Number(selected));
    setConfirming(false);
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 text-sm flex-wrap">
        <span className="text-slate-500">Asignada a:</span>
        <span className="font-medium text-slate-700">
          {currentAssigned
            ? userDisplayName(currentAssigned.full_name, currentAssigned.id)
            : "Sin asignar"}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <select
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value);
            setConfirming(false);
          }}
          disabled={assigning}
          className="flex-1 min-w-0 text-sm border border-slate-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/30"
        >
          <option value="">Seleccionar agente…</option>
          {assignableUsers.map((u) => (
            <option key={u.id} value={u.id}>
              {userDisplayName(u.full_name, u.id)} ({u.role})
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={handlePrimary}
          disabled={assigning || selected === ""}
          className="inline-flex items-center gap-1.5 text-sm font-medium bg-blue-600 text-white rounded-lg px-3 py-1.5 hover:bg-blue-700 disabled:opacity-50 shrink-0"
        >
          {assigning ? <Loader2 className="animate-spin" size={15} /> : <UserCheck size={15} />}
          {isReassign ? "Reasignar" : "Asignar"}
        </button>
      </div>

      {confirming && selectedUser && (
        <div className="text-xs bg-amber-50 border border-amber-200 rounded-lg p-2 flex items-center justify-between gap-2">
          <span className="text-amber-800">
            ¿Reasignar a {userDisplayName(selectedUser.full_name, selectedUser.id)}?
          </span>
          <div className="flex gap-2 shrink-0">
            <button
              onClick={handlePrimary}
              disabled={assigning}
              className="font-bold text-amber-800 hover:underline"
            >
              Confirmar
            </button>
            <button onClick={() => setConfirming(false)} className="text-slate-500 hover:underline">
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
