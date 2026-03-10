"use client";

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { UserPlus, Save, Users, Key, AlertCircle, RefreshCw } from 'lucide-react';

interface StaffUser {
    id: number;
    email: string;
    full_name: string;
    role: string;
}

export default function UserManagement() {
    const { user: currentUser } = useAuth();
    const [users, setUsers] = useState<StaffUser[]>([]);
    const [loading, setLoading] = useState(true);

    const [showAddForm, setShowAddForm] = useState(false);
    const [newUserName, setNewUserName] = useState('');
    const [newUserEmail, setNewUserEmail] = useState('');
    const [newUserPassword, setNewUserPassword] = useState('');
    const [newUserRole, setNewUserRole] = useState('vendedor');

    // UI Feedback
    const [successMessage, setSuccessMessage] = useState("");
    const [errorMessage, setErrorMessage] = useState("");
    const [actionLoading, setActionLoading] = useState(false);

    // Password Update for Current User
    const [showPasswordUpdate, setShowPasswordUpdate] = useState(false);
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');

    useEffect(() => {
        fetchUsers();
    }, [currentUser]);

    const displayMessage = (msg: string, isError = false) => {
        if (isError) {
            setErrorMessage(msg);
            setSuccessMessage("");
        } else {
            setSuccessMessage(msg);
            setErrorMessage("");
        }
        setTimeout(() => {
            setErrorMessage("");
            setSuccessMessage("");
        }, 3000);
    };

    const fetchUsers = async () => {
        if (currentUser?.role !== 'admin') {
            setLoading(false);
            return;
        }
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/users/`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setUsers(data);
            }
        } catch (error) {
            console.error("Error fetching users", error);
        } finally {
            setLoading(false);
        }
    };

    const handleCreateUser = async (e: React.FormEvent) => {
        e.preventDefault();
        setActionLoading(true);
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/users/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    email: newUserEmail,
                    full_name: newUserName,
                    password: newUserPassword,
                    role: newUserRole
                })
            });

            if (res.ok) {
                displayMessage("Usuario creado correctamente");
                setShowAddForm(false);
                setNewUserName('');
                setNewUserEmail('');
                setNewUserPassword('');
                fetchUsers();
            } else {
                const errorData = await res.json();
                displayMessage(errorData.detail || "Error al crear usuario", true);
            }
        } catch (error) {
            displayMessage("Error de conexión al crear usuario", true);
        } finally {
            setActionLoading(false);
        }
    };

    const handleUpdatePassword = async (e: React.FormEvent) => {
        e.preventDefault();
        if (newPassword !== confirmPassword) {
            displayMessage("Las contraseñas no coinciden", true);
            return;
        }

        setActionLoading(true);
        try {
            const token = localStorage.getItem('token');
            // Todos los usuarios pueden cambiar su propia contraseña usando su ID actual
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/users/${currentUser?.id}/password`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    new_password: newPassword
                })
            });

            if (res.ok) {
                displayMessage("Contraseña actualizada exitosamente");
                setShowPasswordUpdate(false);
                setNewPassword('');
                setConfirmPassword('');
            } else {
                displayMessage("Error al actualizar contraseña", true);
            }
        } catch (error) {
            displayMessage("Error de conexión intentando actualizar", true);
        } finally {
            setActionLoading(false);
        }
    };

    return (
        <div className="space-y-6">

            {/* Mensajes de feedback */}
            {successMessage && (
                <div className="p-4 bg-emerald-50 text-emerald-600 border border-emerald-200 rounded-xl flex items-center gap-2">
                    <Save size={18} /> {successMessage}
                </div>
            )}
            {errorMessage && (
                <div className="p-4 bg-red-50 text-red-600 border border-red-200 rounded-xl flex items-center gap-2">
                    <AlertCircle size={18} /> {errorMessage}
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

                {/* Sección de Cambio de Contraseña Personal (Para Todos los Roles) */}
                <div className="bg-white rounded-3xl p-6 shadow-xl shadow-slate-200/50 border border-slate-100 flex flex-col justify-between">
                    <div>
                        <div className="flex items-center gap-3 mb-4">
                            <div className="p-3 bg-blue-50 text-blue-600 rounded-xl">
                                <Key size={24} />
                            </div>
                            <div>
                                <h2 className="text-xl font-bold text-slate-800">Mi Seguridad</h2>
                                <p className="text-sm text-slate-500">Actualiza tu contraseña de acceso temporal o permanentemente.</p>
                            </div>
                        </div>
                    </div>

                    {!showPasswordUpdate ? (
                        <button
                            onClick={() => setShowPasswordUpdate(true)}
                            className="w-full mt-6 py-3 bg-slate-50 hover:bg-slate-100 text-slate-700 font-bold rounded-xl transition-colors border border-slate-200"
                        >
                            Cambiar Mi Contraseña
                        </button>
                    ) : (
                        <form onSubmit={handleUpdatePassword} className="mt-6 space-y-4 animate-in fade-in slide-in-from-bottom-2">
                            <div>
                                <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Nueva Contraseña</label>
                                <input
                                    type="password" required value={newPassword} onChange={e => setNewPassword(e.target.value)}
                                    className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Confirmar Contraseña</label>
                                <input
                                    type="password" required value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)}
                                    className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                                />
                            </div>
                            <div className="flex gap-2">
                                <button type="button" onClick={() => setShowPasswordUpdate(false)} className="flex-1 py-2 text-slate-500 hover:bg-slate-50 font-medium rounded-lg">Cancelar</button>
                                <button type="submit" disabled={actionLoading} className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg flex justify-center items-center gap-2">
                                    {actionLoading ? <RefreshCw className="animate-spin" size={16} /> : "Actualizar"}
                                </button>
                            </div>
                        </form>
                    )}
                </div>

                {/* Sección Exclusiva Admin: Agregar Nuevos Usuarios */}
                {currentUser?.role === 'admin' && (
                    <div className="bg-white rounded-3xl p-6 shadow-xl shadow-slate-200/50 border border-slate-100 flex flex-col justify-between">
                        <div>
                            <div className="flex items-center gap-3 mb-4">
                                <div className="p-3 bg-indigo-50 text-indigo-600 rounded-xl">
                                    <UserPlus size={24} />
                                </div>
                                <div>
                                    <h2 className="text-xl font-bold text-slate-800">Alta de Personal</h2>
                                    <p className="text-sm text-slate-500">Añade a nuevos encargados de ventas o directivos.</p>
                                </div>
                            </div>
                        </div>

                        {!showAddForm ? (
                            <button
                                onClick={() => setShowAddForm(true)}
                                className="w-full mt-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition-colors shadow-md shadow-indigo-600/20"
                            >
                                Crear Nuevo Usuario
                            </button>
                        ) : (
                            <form onSubmit={handleCreateUser} className="mt-4 space-y-3 animate-in fade-in slide-in-from-bottom-2">
                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Nombre Completo</label>
                                        <input required type="text" value={newUserName} onChange={e => setNewUserName(e.target.value)} className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg" placeholder="Ej: Juan Pérez" />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Email</label>
                                        <input required type="email" value={newUserEmail} onChange={e => setNewUserEmail(e.target.value)} className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg" placeholder="juan@unpo.com.ar" />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Contraseña</label>
                                        <input required type="password" value={newUserPassword} onChange={e => setNewUserPassword(e.target.value)} className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg" />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Rol</label>
                                        <select value={newUserRole} onChange={e => setNewUserRole(e.target.value)} className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white">
                                            <option value="vendedor">Vendedor</option>
                                            <option value="admin">Administrador</option>
                                        </select>
                                    </div>
                                </div>
                                <div className="flex gap-2 pt-2">
                                    <button type="button" onClick={() => setShowAddForm(false)} className="flex-1 py-2 text-slate-500 hover:bg-slate-50 text-sm font-medium rounded-lg border border-transparent">Cancelar</button>
                                    <button type="submit" disabled={actionLoading} className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold rounded-lg flex justify-center items-center">
                                        {actionLoading ? <RefreshCw className="animate-spin" size={16} /> : "Registrar"}
                                    </button>
                                </div>
                            </form>
                        )}
                    </div>
                )}
            </div>

            {/* Listado de Personal Existente (Solo visible para admins) */}
            {currentUser?.role === 'admin' && (
                <div className="bg-white rounded-3xl p-6 shadow-xl shadow-slate-200/50 border border-slate-100">
                    <div className="flex items-center gap-3 mb-6">
                        <Users size={20} className="text-slate-400" />
                        <h2 className="text-lg font-bold text-slate-800">Personal Registrado</h2>
                    </div>

                    {loading ? (
                        <div className="text-center py-8 text-slate-400">Cargando usuarios...</div>
                    ) : (
                        <div className="overflow-hidden border border-slate-100 rounded-2xl">
                            <table className="w-full text-left">
                                <thead className="bg-slate-50 text-slate-500 text-[11px] uppercase tracking-widest font-black">
                                    <tr>
                                        <th className="px-6 py-4">Usuario</th>
                                        <th className="px-6 py-4">Rol en el Sistema</th>
                                        <th className="px-6 py-4 text-right">Contacto</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {users.map(u => (
                                        <tr key={u.id} className="hover:bg-slate-50/50">
                                            <td className="px-6 py-4 font-bold text-slate-900 flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center text-xs">
                                                    {u.full_name?.charAt(0) || 'U'}
                                                </div>
                                                {u.full_name}
                                                {u.id === currentUser.id && <span className="text-[10px] bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full uppercase ml-2">Tú</span>}
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className={`text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider ${u.role === 'admin' ? 'bg-indigo-50 text-indigo-600' : 'bg-amber-50 text-amber-600'}`}>
                                                    {u.role}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 text-slate-500 text-sm font-medium text-right">
                                                {u.email}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}

        </div>
    );
}
