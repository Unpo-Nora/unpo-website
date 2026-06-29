"use client";

// Etapa 4.2-A.1 — Scaffolding inicial del Panel de Ventas NORA.
//
// Placeholder visual SIN lógica comercial: no fetchea datos, no renderiza
// tabla/filtros/ordenamiento/acciones y no toca WhatsApp. La tabla, los filtros,
// el ordenamiento y las acciones llegan en subetapas posteriores (4.2-A.2+).
//
// IMPORTANTE: no copia NADA del Panel de Ventas UNPO (SellerDashboard):
// sin CloseSaleModal, sin catálogo/PDF, sin productos, ventas, IVA ni finanzas.

import React from 'react';
import { Construction } from 'lucide-react';

export default function NoraSalesPanel() {
    return (
        <div className="space-y-6">
            <div className="mb-8">
                <h1 className="text-3xl font-serif font-medium text-slate-900">Panel de Ventas NORA</h1>
                <p className="text-slate-500 mt-2">Gestión comercial de prospectos NORA.</p>
            </div>

            <div className="bg-white rounded-3xl shadow-xl shadow-slate-200/50 border border-slate-100 p-12 flex flex-col items-center justify-center text-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center text-slate-400">
                    <Construction size={28} />
                </div>
                <div>
                    <h2 className="text-lg font-bold text-slate-700">Módulo en construcción</h2>
                    <p className="text-slate-400 text-sm mt-1 max-w-md">
                        Scaffolding inicial del Panel de Ventas. El listado de prospectos, los
                        filtros, el ordenamiento y las acciones se incorporarán en las próximas
                        subetapas.
                    </p>
                </div>
            </div>
        </div>
    );
}
