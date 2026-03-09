"use client";

import React, { useState } from 'react';
import { Upload, FileSpreadsheet, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

export default function ImportDashboard() {
    const [file, setFile] = useState<File | null>(null);
    const [status, setStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string>("");

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setStatus('idle');
        }
    };

    const handleUpload = async () => {
        if (!file) return;

        setStatus('uploading');
        const formData = new FormData();
        formData.append('file', file);

        try {
            const token = localStorage.getItem('token');
            const response = await fetch('http://localhost:8000/leads/import/', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData,
            });

            const data = await response.json();

            if (response.ok) {
                setResult(data);
                setStatus('success');
            } else {
                setError(data.detail || "Error al procesar el archivo");
                setStatus('error');
            }
        } catch (err) {
            setError("No se pudo conectar con el servidor");
            setStatus('error');
        }
    };

    return (
        <div className="p-6 bg-white rounded-xl shadow-sm border border-gray-100 max-w-2xl mx-auto">
            <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
                    <FileSpreadsheet size={24} />
                </div>
                <div>
                    <h2 className="text-xl font-bold text-gray-800">Importador de Leads</h2>
                    <p className="text-sm text-gray-500">Sube tus archivos .xlsx o .xlsm (Marketing o Vendedores)</p>
                </div>
            </div>

            <div className="space-y-4">
                <div
                    className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${file ? 'border-blue-200 bg-blue-50' : 'border-gray-200 hover:border-blue-300'
                        }`}
                >
                    <input
                        type="file"
                        id="excel-upload"
                        className="hidden"
                        accept=".xlsx, .xlsm"
                        onChange={handleFileChange}
                    />
                    <label htmlFor="excel-upload" className="cursor-pointer flex flex-col items-center">
                        <Upload className={`mb-3 ${file ? 'text-blue-500' : 'text-gray-400'}`} size={40} />
                        <span className="font-medium text-gray-700">
                            {file ? file.name : "Selecciona o arrastra tu archivo Excel"}
                        </span>
                    </label>
                </div>

                {status === 'idle' && file && (
                    <button
                        onClick={handleUpload}
                        className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl transition-all shadow-lg shadow-blue-200"
                    >
                        Iniciar Importación
                    </button>
                )}

                {status === 'uploading' && (
                    <div className="flex items-center justify-center py-4 text-blue-600">
                        <Loader2 className="animate-spin mr-2" />
                        <span>Procesando archivo...</span>
                    </div>
                )}

                {status === 'success' && (
                    <div className="p-4 bg-green-50 border border-green-100 rounded-xl">
                        <div className="flex items-center gap-2 text-green-700 font-bold mb-2">
                            <CheckCircle size={20} />
                            <span>Importación Completada</span>
                        </div>
                        <div className="text-sm text-green-600 grid grid-cols-3 gap-4">
                            <div>
                                <p className="text-xs text-green-500 uppercase font-bold">Importados</p>
                                <p className="text-lg">{result?.imported}</p>
                            </div>
                            <div>
                                <p className="text-xs text-green-500 uppercase font-bold">Saltados</p>
                                <p className="text-lg">{result?.skipped}</p>
                            </div>
                            <div>
                                <p className="text-xs text-green-500 uppercase font-bold">Total</p>
                                <p className="text-lg">{result?.total_rows}</p>
                            </div>
                        </div>
                    </div>
                )}

                {status === 'error' && (
                    <div className="p-4 bg-red-50 border border-red-100 rounded-xl flex items-start gap-3">
                        <AlertCircle className="text-red-600 shrink-0" size={20} />
                        <div>
                            <p className="font-bold text-red-700 leading-tight">Error</p>
                            <p className="text-sm text-red-600">{error}</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
