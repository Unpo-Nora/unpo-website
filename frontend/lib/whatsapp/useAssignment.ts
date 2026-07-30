"use client";

// Asignación/reasignación de una conversación (solo admin). Aislado del orquestador.

import { useCallback, useState } from "react";
import { whatsappApi } from "./api";
import { ApiError } from "./types";

export interface UseAssignment {
  assigning: boolean;
  assign: (conversationId: number, userId: number) => Promise<void>;
}

export function useAssignment(
  onUnauthorized: () => void,
  onDone: (changed: boolean) => void,
  onError: (msg: string) => void
): UseAssignment {
  const [assigning, setAssigning] = useState(false);

  const assign = useCallback(
    async (conversationId: number, userId: number) => {
      setAssigning(true);
      try {
        const res = await whatsappApi.assign(conversationId, userId);
        onDone(res.changed);
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          onUnauthorized();
          return;
        }
        onError(e instanceof ApiError ? e.message : "No se pudo asignar la conversación");
      } finally {
        setAssigning(false);
      }
    },
    [onDone, onError, onUnauthorized]
  );

  return { assigning, assign };
}
