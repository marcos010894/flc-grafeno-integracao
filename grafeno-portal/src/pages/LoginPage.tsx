import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

const LoginPage: React.FC = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const { signIn } = useAuth();
    const navigate = useNavigate();

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            const response = await api.post('/auth/login', { email, password });
            await signIn(response.data.access_token, response.data.refresh_token);
            navigate('/');
        } catch (err) {
            setError('Credenciais inválidas. Tente novamente.');
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(135deg, var(--bg-dark) 0%, #1e1e2e 100%)'
        }}>
            <div className="card" style={{ width: '100%', maxWidth: '400px' }}>
                <div className="text-center mb-4">
                    <h1 style={{ color: 'var(--primary)', fontSize: '2rem', marginBottom: '0.5rem' }}>FLC Bank</h1>
                    <p className="text-muted">Acesse sua conta</p>
                </div>

                {error && (
                    <div style={{
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        color: 'var(--danger)',
                        padding: '0.75rem',
                        borderRadius: '0.5rem',
                        marginBottom: '1rem',
                        fontSize: '0.875rem'
                    }}>
                        {error}
                    </div>
                )}

                <form onSubmit={handleLogin} className="flex flex-col gap-4">
                    <div>
                        <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem' }}>Email</label>
                        <input
                            type="email"
                            className="w-full"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                            placeholder="seu@email.com"
                        />
                    </div>

                    <div>
                        <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem' }}>Senha</label>
                        <input
                            type="password"
                            className="w-full"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            placeholder="******"
                        />
                    </div>

                    <button
                        type="submit"
                        className="btn btn-primary w-full mt-4"
                        disabled={loading}
                    >
                        {loading ? 'Entrando...' : 'Entrar'}
                    </button>
                </form>
            </div>
        </div>
    );
};

export default LoginPage;
