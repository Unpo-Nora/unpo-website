"use client";

import React, { useEffect, useState } from 'react';
import {
    Briefcase,
    Users,
    Calendar,
    DollarSign,
    CheckCircle,
    UserPlus,
    X,
    FileText,
    Activity,
    CreditCard
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

interface Employee {
    id: number;
    first_name: string;
    last_name: string;
    email?: string;
    phone?: string;
    address?: string;
    role_function?: string;
    salary: number;
    hire_date: string;
    vacation_days_available: number;
    absent_days_this_month: number;
}

export default function HRDashboard() {
    const [employees, setEmployees] = useState<Employee[]>([]);
    const [loading, setLoading] = useState(true);
    const [isEmployeeModalOpen, setIsEmployeeModalOpen] = useState(false);
    const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
    const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
    const [paymentDetails, setPaymentDetails] = useState<any>(null);
    
    // Form state
    const [formData, setFormData] = useState<any>({
        first_name: '',
        last_name: '',
        email: '',
        phone: '',
        address: '',
        role_function: '',
        salary: 0,
        vacation_days_available: 14,
    });

    const { user } = useAuth();
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    const fetchEmployees = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_URL}/hr/employees`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setEmployees(data);
            }
        } catch (error) {
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchEmployees();
    }, []);

    const handleSaveEmployee = async () => {
        try {
            const token = localStorage.getItem('token');
            const url = selectedEmployee ? `${API_URL}/hr/employees/${selectedEmployee.id}` : `${API_URL}/hr/employees`;
            const method = selectedEmployee ? 'PUT' : 'POST';

            const res = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(formData)
            });

            if (res.ok) {
                setIsEmployeeModalOpen(false);
                fetchEmployees();
            } else {
                alert('Hubo un error guardando el empleado.');
            }
        } catch (error) {
            console.error(error);
            alert('Error de conexión.');
        }
    };

    const handleUpdateAbsences = async (empId: number, currentDays: number, increment: boolean) => {
        try {
            const token = localStorage.getItem('token');
            const newAbsences = increment ? currentDays + 1 : Math.max(0, currentDays - 1);
            const res = await fetch(`${API_URL}/hr/employees/${empId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ absent_days_this_month: newAbsences })
            });
            if (res.ok) fetchEmployees();
        } catch (error) {
            console.error(error);
        }
    };

    const handleGeneratePay = async (emp: Employee) => {
        setSelectedEmployee(emp);
        try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${API_URL}/hr/employees/${emp.id}/pay`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setPaymentDetails(data.details);
                setIsPaymentModalOpen(true);
                fetchEmployees(); // absent days might reset
            }
        } catch (error) {
            console.error(error);
        }
    };

    const totalSalaries = employees.reduce((sum, emp) => sum + (emp.salary || 0), 0);

    return (
        <div className="space-y-8 animate-in fade-in duration-700">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h2 className="text-3xl font-black text-slate-900 italic flex items-center gap-2">
                        <Briefcase className="text-indigo-600" size={28} />
                        Recursos Humanos
                    </h2>
                    <p className="text-slate-500 font-medium">Gestión de personal, pagos, licencias y asistencias.</p>
                </div>
                <button
                    onClick={() => {
                        setSelectedEmployee(null);
                        setFormData({
                            first_name: '', last_name: '', email: '', phone: '', address: '', role_function: '', salary: 0, vacation_days_available: 14
                        });
                        setIsEmployeeModalOpen(true);
                    }}
                    className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-2xl shadow-sm transition-colors flex items-center gap-2 flex-shrink-0"
                >
                    <UserPlus size={18} />
                    Alta de Empleado
                </button>
            </div>

            {/* Top Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white p-6 rounded-[32px] shadow-sm border border-slate-100 flex items-center gap-4">
                    <div className="p-4 bg-indigo-50 text-indigo-600 rounded-2xl">
                        <Users size={24} />
                    </div>
                    <div>
                        <p className="text-sm font-bold text-slate-500 uppercase">Plantilla Total</p>
                        <h3 className="text-2xl font-black text-slate-900">{employees.length}</h3>
                    </div>
                </div>
                <div className="bg-white p-6 rounded-[32px] shadow-sm border border-slate-100 flex items-center gap-4">
                    <div className="p-4 bg-emerald-50 text-emerald-600 rounded-2xl">
                        <DollarSign size={24} />
                    </div>
                    <div>
                        <p className="text-sm font-bold text-slate-500 uppercase">Salarios Base Mns.</p>
                        <h3 className="text-2xl font-black text-slate-900">${totalSalaries.toLocaleString('es-AR')}</h3>
                    </div>
                </div>
                <div className="bg-white p-6 rounded-[32px] shadow-sm border border-slate-100 flex items-center gap-4">
                    <div className="p-4 bg-orange-50 text-orange-600 rounded-2xl">
                        <Calendar size={24} />
                    </div>
                    <div>
                        <p className="text-sm font-bold text-slate-500 uppercase">Ausentes Acum. Mes</p>
                        <h3 className="text-2xl font-black text-slate-900">
                            {employees.reduce((sum, emp) => sum + (emp.absent_days_this_month || 0), 0)}
                        </h3>
                    </div>
                </div>
            </div>

            {/* Employee List */}
            <div className="bg-white rounded-[32px] shadow-sm border border-slate-100 overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead className="bg-slate-50">
                            <tr className="text-xs font-black uppercase text-slate-500 tracking-wider">
                                <th className="p-6">Empleado</th>
                                <th className="p-6">Rol / Cargo</th>
                                <th className="p-6">Salario / Paga</th>
                                <th className="p-6">Ausencias (Mes)</th>
                                <th className="p-6 text-center">Acciones</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {loading ? (
                                <tr>
                                    <td colSpan={5} className="p-8 text-center text-slate-500">Cargando personal...</td>
                                </tr>
                            ) : employees.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="p-8 text-center text-slate-500 italic">No hay empleados registrados.</td>
                                </tr>
                            ) : (
                                employees.map((emp) => (
                                    <tr key={emp.id} className="hover:bg-slate-50/50 transition-colors group">
                                        <td className="p-6">
                                            <div className="flex items-center gap-3">
                                                <div className="h-10 w-10 flex items-center justify-center rounded-xl bg-indigo-100 text-indigo-700 font-bold">
                                                    {emp.first_name[0]}{emp.last_name[0]}
                                                </div>
                                                <div>
                                                    <p className="font-bold text-slate-900">{emp.first_name} {emp.last_name}</p>
                                                    <p className="text-xs font-medium text-slate-500">Ingreso: {new Date(emp.hire_date).toLocaleDateString('es-AR')}</p>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="p-6">
                                            <span className="px-3 py-1 bg-slate-100 text-slate-700 font-bold text-xs rounded-full uppercase tracking-wide">
                                                {emp.role_function || 'Sin definir'}
                                            </span>
                                        </td>
                                        <td className="p-6 font-bold text-slate-700">
                                            ${(emp.salary || 0).toLocaleString('es-AR')}
                                            <span className="block text-xs font-medium text-slate-400 mt-1">
                                                Vacaciones: {emp.vacation_days_available} días restantes
                                            </span>
                                        </td>
                                        <td className="p-6">
                                            <div className="flex items-center gap-3">
                                                <button 
                                                    onClick={() => handleUpdateAbsences(emp.id, emp.absent_days_this_month || 0, false)}
                                                    className="w-6 h-6 flex items-center justify-center bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg transition-colors font-black"
                                                >
                                                    -
                                                </button>
                                                <span className={`font-black text-lg ${emp.absent_days_this_month > 0 ? 'text-orange-500' : 'text-slate-400'}`}>
                                                    {emp.absent_days_this_month || 0}
                                                </span>
                                                <button 
                                                    onClick={() => handleUpdateAbsences(emp.id, emp.absent_days_this_month || 0, true)}
                                                    className="w-6 h-6 flex items-center justify-center bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-lg transition-colors font-black"
                                                >
                                                    +
                                                </button>
                                            </div>
                                        </td>
                                        <td className="p-6 text-center">
                                            <div className="flex items-center justify-center gap-2 opacity-100 md:opacity-0 group-hover:opacity-100 transition-opacity">
                                                <button
                                                    onClick={() => {
                                                        setSelectedEmployee(emp);
                                                        setFormData(emp);
                                                        setIsEmployeeModalOpen(true);
                                                    }}
                                                    className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-lg transition-colors"
                                                >
                                                    Editar
                                                </button>
                                                <button
                                                    onClick={() => handleGeneratePay(emp)}
                                                    className="px-3 py-1.5 bg-emerald-100 hover:bg-emerald-200 text-emerald-700 text-xs font-bold rounded-lg transition-colors flex items-center gap-1"
                                                >
                                                    <CreditCard size={14} /> Pagar & Recibo
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Employee Modal */}
            {isEmployeeModalOpen && (
                <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-[32px] shadow-xl w-full max-w-xl overflow-hidden animate-in zoom-in-95 duration-200">
                        <div className="p-6 border-b border-slate-100 flex items-center justify-between">
                            <h3 className="text-xl font-black text-slate-900 italic">
                                {selectedEmployee ? 'Editar Empleado' : 'Nuevo Empleado'}
                            </h3>
                            <button onClick={() => setIsEmployeeModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                                <X size={24} />
                            </button>
                        </div>
                        <div className="p-6 space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1">
                                    <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Nombre</label>
                                    <input type="text" value={formData.first_name} onChange={e => setFormData({...formData, first_name: e.target.value})} className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 font-bold text-slate-800" />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Apellido</label>
                                    <input type="text" value={formData.last_name} onChange={e => setFormData({...formData, last_name: e.target.value})} className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 font-bold text-slate-800" />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1">
                                    <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Cargo / Rol</label>
                                    <input type="text" value={formData.role_function} onChange={e => setFormData({...formData, role_function: e.target.value})} className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 font-bold text-slate-800" placeholder="Ej. Vendedor Senior" />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Salario Base ($)</label>
                                    <input type="number" value={formData.salary} onChange={e => setFormData({...formData, salary: parseFloat(e.target.value)})} className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 font-black text-indigo-700" />
                                </div>
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Teléfono / Celular</label>
                                <input type="text" value={formData.phone} onChange={e => setFormData({...formData, phone: e.target.value})} className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 font-bold text-slate-800" />
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Dirección</label>
                                <input type="text" value={formData.address} onChange={e => setFormData({...formData, address: e.target.value})} className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 font-bold text-slate-800" />
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-1">
                                    <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Días Vacaciones Mín.</label>
                                    <input type="number" value={formData.vacation_days_available} onChange={e => setFormData({...formData, vacation_days_available: parseInt(e.target.value)})} className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 font-bold text-slate-800" />
                                </div>
                            </div>
                        </div>
                        <div className="p-6 bg-slate-50 flex justify-end gap-3 rounded-b-[32px]">
                            <button onClick={() => setIsEmployeeModalOpen(false)} className="px-5 py-2.5 text-slate-600 font-bold hover:bg-slate-200 rounded-xl transition-colors">Cancelar</button>
                            <button onClick={handleSaveEmployee} className="px-5 py-2.5 bg-indigo-600 text-white font-bold rounded-xl hover:bg-indigo-700 shadow-md transition-colors flex items-center gap-2">
                                <CheckCircle size={18} /> Guardar
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Payment / Payload Generation Modal */}
            {isPaymentModalOpen && paymentDetails && selectedEmployee && (
                <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-md z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-[32px] shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
                        <div className="p-8 text-center space-y-4">
                            <div className="w-20 h-20 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-6 shadow-inner">
                                <CheckCircle size={40} />
                            </div>
                            <h3 className="text-3xl font-black text-slate-900 italic">Pago Generado</h3>
                            <p className="text-slate-500 font-medium">Se ha calculado la liquidación de <strong className="text-slate-800">{selectedEmployee.first_name} {selectedEmployee.last_name}</strong>.</p>
                            
                            <div className="bg-slate-50 rounded-2xl p-6 space-y-4 my-6 text-left border border-slate-100">
                                <div className="flex justify-between items-center text-sm font-bold">
                                    <span className="text-slate-500">Salario Base:</span>
                                    <span className="text-slate-800">${paymentDetails.base_salary.toLocaleString('es-AR')}</span>
                                </div>
                                <div className="flex justify-between items-center text-sm font-bold text-blue-600">
                                    <span>Comisiones (Estimado):</span>
                                    <span>+ ${paymentDetails.commissions.toLocaleString('es-AR')}</span>
                                </div>
                                <div className="flex justify-between items-center text-sm font-bold text-orange-600">
                                    <span>Ausencias ({selectedEmployee.absent_days_this_month}):</span>
                                    <span>- (A calcular)</span>
                                </div>
                                <div className="pt-4 border-t border-slate-200 flex justify-between items-center text-xl font-black text-emerald-600">
                                    <span>Total a Pagar:</span>
                                    <span>${paymentDetails.total_payout.toLocaleString('es-AR')}</span>
                                </div>
                            </div>
                            
                            <p className="text-xs text-slate-400 italic mb-6">
                                Las ausencias de este mes han sido reiniciadas a 0. Se puede generar un PDF o Excel de recibo de sueldo a partir de esta información en futuras actualizaciones.
                            </p>

                            <button onClick={() => setIsPaymentModalOpen(false)} className="w-full py-4 rounded-xl bg-slate-900 text-white font-bold text-lg hover:bg-slate-800 transition-colors">
                                Volver al Panel
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
