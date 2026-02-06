import React, { useEffect, useState } from 'react';
import api from '../services/api';


const Statement: React.FC = () => {
    const [extract, setExtract] = useState<any>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function fetchExtract() {
            try {
                console.log('Fetching statement from /grafeno-client/statement...');
                const response = await api.get('/grafeno-client/statement');
                console.log('Statement API Response:', response.data);

                // Structure from grafeno_client router
                const list = response.data?.data?.data || [];
                console.log('Extracted list:', list);
                console.log('List length:', list.length);

                setExtract(list);
            } catch (error: any) {
                console.error("Error fetching extract", error);
                if (error.response) {
                    console.error("Error response:", error.response.data);
                    console.error("Error status:", error.response.status);
                }
            } finally {
                setLoading(false);
            }
        }
        fetchExtract();
    }, []);

    if (loading) return <div className="container">Carregando...</div>;

    return (
        <div className="container">
            <h1 className="text-2xl mb-4">Extrato Grafeno</h1>

            <div className="card p-0 table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Data</th>
                            <th>Descrição</th>
                            <th>Documento</th>
                            <th style={{ textAlign: 'right' }}>Valor</th>
                        </tr>
                    </thead>
                    <tbody>
                        {extract.map((entry: any, index: number) => {
                            const attr = entry.attributes || {};
                            const date = new Date(attr.entryAt);
                            const value = Number(attr.value || 0);
                            const bankAccount = attr.bankAccount || {};

                            return (
                                <tr key={entry.id || index}>
                                    <td>{date.toLocaleDateString('pt-BR')} {date.toLocaleTimeString('pt-BR')}</td>
                                    <td>
                                        <div className="flex flex-col">
                                            <span>{attr.kind || 'Movimentação'}</span>
                                            <span className="text-sm text-muted">{bankAccount.name || '-'}</span>
                                        </div>
                                    </td>
                                    <td>
                                        <span className="text-sm text-muted">{bankAccount.documentNumber || '-'}</span>
                                    </td>
                                    <td style={{ textAlign: 'right', fontWeight: 600, color: value >= 0 ? 'var(--success)' : 'var(--text-main)' }}>
                                        {value >= 0 ? '+' : ''} {value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                    </td>
                                </tr>
                            );
                        })}

                        {extract.length === 0 && (
                            <tr>
                                <td colSpan={4} className="text-center p-8 text-muted">
                                    Nenhuma movimentação encontrada.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default Statement;
