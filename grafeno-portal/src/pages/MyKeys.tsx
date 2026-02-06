import React, { useEffect } from 'react';
import { Copy, Key } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const MyKeys: React.FC = () => {
    const { user } = useAuth();

    useEffect(() => {
        // Only using user context key
    }, []);

    const copy = (text: string) => {
        navigator.clipboard.writeText(text);
        alert('Copiado!');
    };

    return (
        <div className="container">
            <h1 className="text-2xl mb-4">Minhas Chaves Pix</h1>

            <div className="card">
                <h3 className="mb-4 text-primary font-bold">Chaves Cadastradas (Grafeno)</h3>

                {user?.pix_key ? (
                    <div className="flex items-center justify-between p-3 border-b border-gray-700">
                        <div className="flex items-center gap-3">
                            <Key size={18} className="text-muted" />
                            <div>
                                <p className="font-bold">{user.pix_key}</p>
                                <span className="badge badge-success">Chave Principal</span>
                            </div>
                        </div>
                        <button onClick={() => copy(user.pix_key!)} className="btn btn-outline btn-sm">
                            <Copy size={14} />
                        </button>
                    </div>
                ) : (
                    <p className="text-muted">Nenhuma chave encontrada.</p>
                )}
            </div>
        </div>
    );
};

export default MyKeys;
