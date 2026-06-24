"use client";

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import {
    Users,
    LogOut,
    UserCircle,
    X
} from 'lucide-react';

interface NoraSidebarProps {
    isOpen?: boolean;
    setIsOpen?: (val: boolean) => void;
}

// Sidebar propio del CRM NORA. Branding NORA, sin referencias UNPO.
// Aislado: todavia no se usa en ninguna ruta (se integrara en /nora-admin).
export default function NoraSidebar({ isOpen = false, setIsOpen }: NoraSidebarProps) {
    const { user, logout } = useAuth();
    const pathname = usePathname();

    const menuItems = [
        {
            title: 'Waitlist / Leads NORA',
            path: '/nora-admin',
            icon: <Users size={20} />,
        }
    ];

    return (
        <aside className={`
            fixed lg:static inset-y-0 left-0 z-50
            w-64 bg-slate-900 text-slate-300 flex flex-col h-full border-r border-slate-800
            transform transition-transform duration-300 ease-in-out
            ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
            shrink-0
        `}>
            {/* Brand */}
            <div className="p-6 border-b border-slate-800 mb-6 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3 overflow-hidden">
                    <div className="w-8 h-8 bg-white text-slate-900 rounded flex items-center justify-center font-serif font-bold shrink-0">
                        N
                    </div>
                    <div className="overflow-hidden">
                        <h1 className="text-white font-serif font-medium tracking-wide truncate">NORA</h1>
                        <p className="text-xs text-slate-500 truncate">Gestión de Leads</p>
                    </div>
                </div>
                {setIsOpen && (
                    <button onClick={() => setIsOpen(false)} className="lg:hidden p-2 -mr-2 text-slate-400 hover:text-white rounded-lg shrink-0">
                        <X size={20} />
                    </button>
                )}
            </div>

            {/* Navigation */}
            <nav className="flex-1 px-4 space-y-1">
                {menuItems.map((item) => {
                    const isActive = pathname === item.path;
                    return (
                        <Link
                            key={item.path}
                            href={item.path}
                            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${isActive
                                ? 'bg-white/10 text-white font-bold'
                                : 'hover:bg-slate-800 hover:text-white'
                                }`}
                        >
                            {item.icon}
                            <span>{item.title}</span>
                        </Link>
                    );
                })}
            </nav>

            {/* User & Footer */}
            <div className="p-4 border-t border-slate-800">
                <div className="flex items-center gap-3 p-3 rounded-xl bg-slate-800/50 mb-4">
                    <UserCircle size={32} className="text-slate-400" />
                    <div className="overflow-hidden">
                        <p className="text-sm font-bold text-white truncate">{user?.full_name}</p>
                        <p className="text-xs text-slate-500 capitalize">{user?.role}</p>
                    </div>
                </div>

                <button
                    onClick={logout}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-slate-300 hover:bg-white/10 hover:text-white transition-all font-medium"
                >
                    <LogOut size={20} />
                    <span>Cerrar Sesión</span>
                </button>
            </div>
        </aside>
    );
}
