"use client";

import React from 'react';
import InventoryDashboard from '@/components/dashboard/InventoryDashboard';
import { useAuth } from '@/context/AuthContext';
import { useRouter } from 'next/navigation';

export default function InventoryPage() {
    const { user, loading } = useAuth();
    const router = useRouter();

    React.useEffect(() => {
        if (!loading && (!user || user.role !== 'admin')) {
            router.push('/login');
        }
    }, [user, loading, router]);

    if (loading || !user) return <div className="flex items-center justify-center h-screen">Cargando...</div>;

    return (
        <>
            <header className="flex justify-between items-end mb-8">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Gestión de Inventario</h1>
                    <p className="text-slate-500 mt-1">Control de stock, precios y catálogo de productos.</p>
                </div>
            </header>

            <InventoryDashboard />
        </>
    );
}
