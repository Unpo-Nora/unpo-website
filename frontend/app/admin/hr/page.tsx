"use client";

import ProtectedRoute from '@/components/auth/ProtectedRoute';
import Sidebar from '@/components/dashboard/Sidebar';
import HRDashboard from '@/components/dashboard/HRDashboard';
import { useAuth } from '@/context/AuthContext';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function HRPage() {
    const { user } = useAuth();
    const router = useRouter();

    useEffect(() => {
        if (user && user.role !== 'admin') {
            router.push('/sales');
        }
    }, [user, router]);

    return (
        <ProtectedRoute>
            <div className="flex h-screen bg-slate-50">
                <Sidebar />
                <main className="flex-1 overflow-y-auto p-4 md:p-8 custom-scrollbar">
                    <HRDashboard />
                </main>
            </div>
        </ProtectedRoute>
    );
}
