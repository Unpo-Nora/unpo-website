"use client";

import React from "react";

export default function UnreadBadge({ count, className = "" }: { count: number; className?: string }) {
  if (!count || count <= 0) return null;
  return (
    <span
      className={`inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-green-600 text-white text-xs font-bold ${className}`}
      aria-label={`${count} mensajes sin leer`}
    >
      {count > 99 ? "99+" : count}
    </span>
  );
}
