"use client";

import React, { createContext, useContext, useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

interface User {
    id: number;
    email: string;
    full_name: string;
    role: string;
}

interface AuthContextType {
    user: User | null;
    loading: boolean;
    login: (token: string) => Promise<void>;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);
    const router = useRouter();

    useEffect(() => {
        const token = localStorage.getItem('token');
        if (token) {
            validateToken(token);
        } else {
            setLoading(false);
        }
    }, []);

    const validateToken = async (token: string) => {
        try {
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/auth/me`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const userData = await response.json();
                setUser(userData);
                return userData;
            } else {
                localStorage.removeItem('token');
                return null;
            }
        } catch (err) {
            console.error("Auth validation failed", err);
            return null;
        } finally {
            setLoading(false);
        }
    };

    const login = async (token: string) => {
        localStorage.setItem('token', token);
        const userData = await validateToken(token);

        // Redirección inteligente
        if (userData?.role === 'admin') {
            router.push('/admin/sales'); // Podría ser un dashboard general
        } else {
            router.push('/admin/sales');
        }
    };

    const logout = () => {
        localStorage.removeItem('token');
        setUser(null);
        router.push('/');
    };

    return (
        <AuthContext.Provider value={{ user, loading, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
