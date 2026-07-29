"use client";

import React from "react";
import { MessageSquare } from "lucide-react";

export default function WhatsAppEmptyState({
  title,
  description,
  icon,
}: {
  title: string;
  description?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-slate-400">
      <div className="mb-3 text-slate-300">{icon ?? <MessageSquare size={40} />}</div>
      <p className="text-slate-600 font-medium">{title}</p>
      {description && <p className="text-sm text-slate-400 mt-1 max-w-xs">{description}</p>}
    </div>
  );
}
