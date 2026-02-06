import React from 'react';
import { NavLink } from 'react-router-dom';
import {
    LayoutDashboard,
    ArrowRightLeft,
    QrCode,
    Wallet,
    Users,
    LogOut,
    Key
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const Sidebar: React.FC = () => {
    const { signOut, user } = useAuth();

    const navItems = [
        { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
        { icon: QrCode, label: 'Cobrar PIX', path: '/charge' },
        { icon: ArrowRightLeft, label: 'Enviar PIX', path: '/send' },
        { icon: Wallet, label: 'Extrato', path: '/statement' },
        { icon: Users, label: 'Beneficiários', path: '/beneficiaries' },
        { icon: Key, label: 'Minhas Chaves', path: '/keys' },
    ];

    return (
        <div className="sidebar" style={{
            width: '260px',
            backgroundColor: 'var(--bg-card)',
            height: '100vh',
            display: 'flex',
            flexDirection: 'column',
            borderRight: '1px solid var(--bg-hover)',
            position: 'fixed'
        }}>
            <div style={{ padding: '2rem', borderBottom: '1px solid var(--bg-hover)' }}>
                <h2 style={{ color: 'var(--primary)', fontWeight: 'bold', fontSize: '1.5rem' }}>FLC Bank</h2>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Portal Grafeno</p>
            </div>

            <nav style={{ flex: 1, padding: '2rem 1rem' }}>
                <div className="flex flex-col gap-2">
                    {navItems.map((item) => (
                        <NavLink
                            key={item.path}
                            to={item.path}
                            style={({ isActive }) => ({
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.75rem',
                                padding: '0.75rem 1rem',
                                borderRadius: '0.5rem',
                                color: isActive ? 'var(--primary)' : 'var(--text-muted)',
                                backgroundColor: isActive ? 'rgba(0, 208, 156, 0.1)' : 'transparent',
                                fontWeight: isActive ? 600 : 400,
                                transition: 'all 0.2s',
                            })}
                        >
                            <item.icon size={20} />
                            {item.label}
                        </NavLink>
                    ))}
                </div>
            </nav>

            <div style={{ padding: '1.5rem', borderTop: '1px solid var(--bg-hover)' }}>
                <div style={{ marginBottom: '1rem' }}>
                    <p style={{ fontWeight: 600 }}>{user?.full_name}</p>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{user?.email}</p>
                </div>
                <button
                    onClick={signOut}
                    className="btn btn-outline w-full"
                    style={{ justifyContent: 'center' }}
                >
                    <LogOut size={18} />
                    Sair
                </button>
            </div>
        </div>
    );
};

export default Sidebar;
