"use client";

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import {
    LayoutDashboard,
    Users,
    FileUp,
    LogOut,
    Settings,
    UserCircle,
    Star,
    MonitorSmartphone
} from 'lucide-react';

export default function Sidebar() {
    console.log("Sidebar Mounted at:", new Date().toLocaleTimeString());
    const { user, loading, logout } = useAuth();
    const pathname = usePathname();

    console.log("Sidebar Rendering - Current User:", user?.email, "Role:", user?.role);

    const menuItems = [
        {
            title: 'Estadísticas',
            path: '/admin/analytics',
            icon: <LayoutDashboard size={20} />,
            roles: ['admin']
        },
        {
            title: 'Panel de Ventas',
            path: '/admin/sales',
            icon: <Users size={20} />,
            roles: ['admin', 'vendedor']
        },
        {
            title: 'Clientes',
            path: '/admin/clients',
            icon: <Star size={20} />,
            roles: ['admin', 'vendedor']
        },
        {
            title: 'Inventario',
            path: '/admin/inventory',
            icon: <Settings size={20} />,
            roles: ['admin']
        },
        {
            title: 'Importar Leads',
            path: '/admin/import',
            icon: <FileUp size={20} />,
            roles: ['admin', 'vendedor']
        },
        {
            title: 'Personal y Seguridad',
            path: '/admin/users',
            icon: <Users size={20} />,
            roles: ['admin', 'vendedor']
        },
        {
            title: 'Waitlist NORA',
            path: '/admin/nora',
            icon: <MonitorSmartphone size={20} />,
            roles: ['admin']
        }
    ];

    const filteredItems = menuItems.filter(item =>
        !item.roles || (user && item.roles.includes(user.role))
    );

    return (
        <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col h-screen sticky top-0 border-r border-slate-800">
            {/* Brand */}
            <div className="p-6 border-b border-slate-800 mb-6">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-red-600 rounded flex items-center justify-center text-white font-bold italic">
                        U
                    </div>
                    <div>
                        <h1 className="text-white font-bold tracking-tight">UNPO Control Center</h1>
                        <p className="text-xs text-slate-500">Gestión de Inventario y Leads</p>
                    </div>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 px-4 space-y-1">
                {filteredItems.map((item) => {
                    const isActive = pathname === item.path;
                    return (
                        <Link
                            key={item.path}
                            href={item.path}
                            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${isActive
                                ? 'bg-blue-600/10 text-blue-400 font-bold'
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
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-red-400 hover:bg-red-500/10 transition-all font-medium"
                >
                    <LogOut size={20} />
                    <span>Cerrar Sesión</span>
                </button>
            </div>
        </aside>
    );
}
