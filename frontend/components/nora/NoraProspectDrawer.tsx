"use client";

// Etapa 4.3 — Ficha/detalle del prospecto NORA (drawer lateral, estilo Clienty).
//
// Componente PRESENTACIONAL: recibe el prospecto seleccionado y callbacks. No
// fetchea, no usa AuthContext ni llama APIs; las acciones (WhatsApp / cambio de
// estado) se delegan al panel. Read-only salvo el cambio de estado básico.
//
// Muestra: Estado, Asignado a, Fecha de ingreso, Canal de adquisición, Landing/
// origen, Nombre, Teléfono, Email, Mensaje, Etiquetas y Notas. Incluye una zona
// de "Conversación de WhatsApp" PREPARADA pero vacía: la integración real
// (WhatsApp Business API) se conectará en una etapa futura con trabajo de backend.
// Hoy el botón WhatsApp es un deep link wa.me, no la API de conversación.

import React from 'react';
import {
    X,
    MessageCircle,
    User,
    Phone,
    Mail,
    CalendarDays,
    Radio,
    MapPin,
    Tag,
    StickyNote,
    MessageSquareText,
} from 'lucide-react';
import type { NoraLead } from './types';
import NoraStatusBadge from './NoraStatusBadge';
import { formatDate, channelLabel } from '@/lib/nora/format';

interface NoraProspectDrawerProps {
    /** Prospecto a mostrar; null/cerrado si no hay selección. */
    lead: NoraLead | null;
    onClose: () => void;
    onWhatsApp: (lead: NoraLead) => void;
    onStatusChange: (lead: NoraLead, status: string) => void;
    /** True mientras se actualiza este prospecto (deshabilita controles). */
    updating: boolean;
}

const DETAIL_STATUS_SELECT =
    'text-sm font-bold rounded-lg border border-slate-200 bg-white py-2 px-3 text-slate-700 focus:ring-2 focus:ring-slate-200 outline-none disabled:opacity-40';

export default function NoraProspectDrawer({
    lead,
    onClose,
    onWhatsApp,
    onStatusChange,
    updating,
}: NoraProspectDrawerProps) {
    if (!lead) return null;

    const hasPhone = Boolean(lead.phone && lead.phone.trim());
    const channel = channelLabel(lead.source, lead.platform);
    const knownStatus = ['NEW', 'CONTACTED', 'CLIENT'].includes(lead.status);

    // "Landing / origen": se arma con datos de tracking reales del Lead.
    const origenParts = [lead.source, lead.platform, lead.campaign].filter(
        (v): v is string => Boolean(v && v.trim())
    );
    const origen = origenParts.length > 0 ? origenParts.join(' · ') : '—';

    return (
        <div className="fixed inset-0 z-50 flex justify-end">
            {/* Overlay */}
            <div
                className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
                onClick={onClose}
                aria-hidden
            />

            {/* Panel */}
            <aside className="relative w-full max-w-md bg-white h-full shadow-2xl flex flex-col animate-in slide-in-from-right">
                {/* Header */}
                <div className="px-6 py-5 border-b border-slate-100 flex items-start justify-between gap-3 shrink-0">
                    <div className="min-w-0">
                        <div className="text-[11px] font-black uppercase tracking-widest text-slate-400">Prospecto</div>
                        <h2 className="text-xl font-serif font-medium text-slate-900 truncate">
                            {lead.full_name || 'Sin nombre'}
                        </h2>
                        <div className="mt-2">
                            <NoraStatusBadge status={lead.status} />
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="p-2 -mr-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg shrink-0"
                        title="Cerrar"
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Acciones rápidas */}
                <div className="px-6 py-4 border-b border-slate-100 flex flex-wrap items-center gap-3 shrink-0">
                    <button
                        type="button"
                        onClick={() => onWhatsApp(lead)}
                        disabled={!hasPhone || updating}
                        className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-bold rounded-xl bg-slate-900 hover:bg-slate-800 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                        title={hasPhone ? 'Contactar por WhatsApp' : 'Sin teléfono válido'}
                    >
                        <MessageCircle size={18} />
                        WhatsApp
                    </button>
                    <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-400 uppercase tracking-wide">Estado</span>
                        <select
                            aria-label="Cambiar estado del prospecto"
                            className={DETAIL_STATUS_SELECT}
                            value={knownStatus ? lead.status : ''}
                            disabled={updating}
                            onChange={(e) => onStatusChange(lead, e.target.value)}
                        >
                            {!knownStatus && (
                                <option value="" disabled>
                                    {lead.status}
                                </option>
                            )}
                            <option value="NEW">Nuevo</option>
                            <option value="CONTACTED">Contactado</option>
                            <option value="CLIENT">Cliente</option>
                        </select>
                    </div>
                </div>

                {/* Cuerpo scrolleable */}
                <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
                    {/* Datos del prospecto */}
                    <section>
                        <SectionTitle>Datos del prospecto</SectionTitle>
                        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-4">
                            <Field icon={<User size={15} />} label="Nombre" value={lead.full_name || '—'} />
                            <Field icon={<Phone size={15} />} label="Teléfono" value={lead.phone || '—'} />
                            <Field icon={<Mail size={15} />} label="Email" value={lead.email || '—'} />
                            <Field
                                icon={<User size={15} />}
                                label="Asignado a"
                                value={lead.seller ? lead.seller.split('@')[0] : 'Sin asignar'}
                            />
                            <Field
                                icon={<CalendarDays size={15} />}
                                label="Fecha de ingreso"
                                value={formatDate(lead.lead_date || lead.created_at)}
                            />
                            <Field icon={<Radio size={15} />} label="Canal de adquisición" value={channel} />
                            <Field icon={<MapPin size={15} />} label="Landing / origen" value={origen} full />
                        </dl>
                    </section>

                    {/* Mensaje (interés/consulta que dejó el prospecto) */}
                    <section>
                        <SectionTitle icon={<MessageSquareText size={14} />}>Mensaje</SectionTitle>
                        <p className="text-sm text-slate-600 bg-slate-50 border border-slate-100 rounded-xl px-4 py-3 whitespace-pre-wrap">
                            {lead.product_interest?.trim() || 'Sin mensaje registrado.'}
                        </p>
                    </section>

                    {/* Etiquetas */}
                    <section>
                        <SectionTitle icon={<Tag size={14} />}>Etiquetas</SectionTitle>
                        <div className="flex flex-wrap gap-2">
                            {channel !== '—' ? (
                                <span className="inline-flex items-center text-[11px] font-bold uppercase tracking-wide text-slate-600 bg-slate-100 border border-slate-200 px-2.5 py-1 rounded-full">
                                    {channel}
                                </span>
                            ) : (
                                <span className="text-sm text-slate-400 italic">Sin etiquetas todavía.</span>
                            )}
                        </div>
                    </section>

                    {/* Notas */}
                    <section>
                        <SectionTitle icon={<StickyNote size={14} />}>Notas</SectionTitle>
                        <p className="text-sm text-slate-600 italic whitespace-pre-wrap">
                            {lead.notes?.trim() || 'Sin notas.'}
                        </p>
                    </section>

                    {/* Conversación de WhatsApp (estructura preparada, sin API real) */}
                    <section>
                        <SectionTitle icon={<MessageCircle size={14} />}>Conversación de WhatsApp</SectionTitle>
                        <div className="border border-dashed border-slate-200 rounded-2xl bg-slate-50/60 p-6 text-center">
                            <MessageCircle className="mx-auto text-slate-300" size={28} />
                            <p className="text-sm font-bold text-slate-500 mt-3">Aún no hay conversación</p>
                            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                                La integración con WhatsApp Business se conectará en una etapa futura.
                                Por ahora el botón “WhatsApp” abre un chat directo (deep link).
                            </p>
                        </div>
                    </section>
                </div>
            </aside>
        </div>
    );
}

function SectionTitle({ children, icon }: { children: React.ReactNode; icon?: React.ReactNode }) {
    return (
        <h3 className="text-[11px] font-black uppercase tracking-widest text-slate-400 mb-3 flex items-center gap-2">
            {icon}
            {children}
        </h3>
    );
}

interface FieldProps {
    icon: React.ReactNode;
    label: string;
    value: string;
    full?: boolean;
}

function Field({ icon, label, value, full }: FieldProps) {
    return (
        <div className={`min-w-0 ${full ? 'sm:col-span-2' : ''}`}>
            <div className="text-[10px] font-black uppercase tracking-widest text-slate-400 flex items-center gap-1.5">
                <span className="text-slate-300">{icon}</span>
                {label}
            </div>
            <div className="text-sm text-slate-700 mt-1 break-words">{value}</div>
        </div>
    );
}
