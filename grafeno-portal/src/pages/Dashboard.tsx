import React, { useEffect, useState } from 'react';
import { ArrowDownLeft, Wallet } from 'lucide-react';
import api from '../services/api';

const Dashboard: React.FC = () => {
    const [balance, setBalance] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [errorMsg, setErrorMsg] = useState('');

    useEffect(() => {
        async function fetchBalance() {
            try {
                console.log('Fetching balance from /grafeno-client/balance...');
                const response = await api.get('/grafeno-client/balance');
                console.log('Balance Response:', response.data);

                if (response.data.success === false) {
                    setErrorMsg(response.data.error || 'Erro desconhecido da API');
                }

                setBalance(response.data);
            } catch (error: any) {
                console.error("Error fetching balance", error);
                setErrorMsg(error.response?.data?.detail || 'Erro de conexão/Auth');
            } finally {
                setLoading(false);
            }
        }
        fetchBalance();
    }, []);

    if (loading) return <div className="container">Carregando...</div>;

    // Show error if blocked/failed
    if (errorMsg) {
        return (
            <div className="container text-center">
                <div className="alert alert-danger" style={{ color: 'var(--danger)', padding: '2rem', border: '1px solid var(--danger)', borderRadius: '8px' }}>
                    <h3>Erro ao carregar saldo</h3>
                    <p>{errorMsg}</p>
                    <button onClick={() => window.location.href = '/login'} className="btn btn-outline mt-4">Fazer Login Novamente</button>
                </div>
            </div>
        );
    }

    return (
        <div className="container">
            <h1 className="text-2xl mb-4">Dashboard Grafeno</h1>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
                {/* Main Balance Card */}
                <div className="card" style={{ background: 'linear-gradient(135deg, var(--primary-dark), var(--primary))', color: '#fff' }}>
                    <div className="flex items-center gap-2 mb-2">
                        <Wallet size={20} />
                        <span style={{ opacity: 0.9 }}>Saldo Disponível</span>
                    </div>
                    <div style={{ fontSize: '2.5rem', fontWeight: 700 }}>
                        {Number(balance?.available_balance || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                    </div>
                    {balance?.account_number && (
                        <div style={{ marginTop: '1rem', fontSize: '0.875rem', opacity: 0.8 }}>
                            Conta: {balance.account_number} | Ag: {balance.agency}
                        </div>
                    )}
                </div>

                {/* Current Balance (Blocked + Liquid) */}
                <div className="card">
                    <div className="flex items-center gap-2 mb-2 text-muted">
                        <ArrowDownLeft size={20} />
                        <span>Saldo Total (em conta)</span>
                    </div>
                    <div className="text-xl">
                        {Number(balance?.current_balance || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                    </div>
                </div>
            </div>

        </div>
    );
};

export default Dashboard;
