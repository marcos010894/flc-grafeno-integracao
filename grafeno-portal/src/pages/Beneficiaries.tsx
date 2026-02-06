import React, { useState, useEffect } from 'react';
import api from '../services/api';
import { User, RefreshCw, UserPlus } from 'lucide-react';
import Toast, { type ToastType } from '../components/Toast';

export interface Beneficiary {
    id: string;
    name: string;
    pixKey: string;
    keyType: string;
    document?: string;
}

const Beneficiaries: React.FC = () => {
    const [list, setList] = useState<Beneficiary[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [showForm, setShowForm] = useState(false);
    const [name, setName] = useState('');
    const [pixKey, setPixKey] = useState('');
    const [keyType, setKeyType] = useState('CPF');
    const [doc, setDoc] = useState('');

    // Toast State
    const [toast, setToast] = useState<{ msg: string, type: ToastType } | null>(null);

    const showToast = (msg: string, type: ToastType) => {
        setToast({ msg, type });
    };

    const fetchBeneficiaries = async () => {
        setLoading(true);
        try {
            const response = await api.get('/grafeno-client/beneficiaries');

            // Check structure
            let items: any[] = [];
            if (response.data?.data?.data) {
                items = response.data.data.data;
            } else if (Array.isArray(response.data?.data)) {
                // Sometimes might return list directly?
                items = response.data.data;
            }

            const mappedList = items.map((item: any) => ({
                id: item.id,
                name: item.attributes?.name || 'Sem Nome',
                pixKey: item.attributes?.pixDetails?.key || 'N/A',
                keyType: item.attributes?.pixDetails?.keyType || 'bancario',
                document: item.attributes?.documentNumber
            }));
            setList(mappedList);

        } catch (error: any) {
            console.error("Erro ao buscar beneficiários", error);
        } finally {
            setLoading(false);
        }
    };

    const handleAdd = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        try {
            await api.post('/grafeno-client/beneficiaries', {
                name,
                documentNumber: doc,
                pixKey,
                keyType
            });

            showToast('Beneficiário cadastrado com sucesso!', 'success');

            setShowForm(false);
            setName('');
            setPixKey('');
            setDoc('');
            fetchBeneficiaries();
        } catch (error: any) {
            console.error(error);
            const msg = error.response?.data?.detail || error.message || 'Erro desconhecido';
            // Limpar prefixos técnicos se existirem
            const cleanMsg = msg.replace('base: ', '').replace('errors: ', '');
            showToast(cleanMsg, 'error');
        } finally {
            setSaving(false);
        }
    };

    useEffect(() => {
        fetchBeneficiaries();
    }, []);

    return (
        <div className="container">
            {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}

            <div className="flex justify-between items-center mb-4">
                <h1 className="text-2xl">Beneficiários (Grafeno)</h1>
                <div className="flex gap-2">
                    <button onClick={fetchBeneficiaries} className="btn btn-outline btn-sm">
                        <RefreshCw size={18} />
                    </button>
                    <button onClick={() => setShowForm(!showForm)} className="btn btn-primary">
                        <UserPlus size={18} />
                        Novo
                    </button>
                </div>
            </div>

            {showForm && (
                <div className="card mb-4 animate-fade-in">
                    <h3 className="mb-2">Adicionar Beneficiário</h3>
                    <form onSubmit={handleAdd} className="flex flex-col gap-4">
                        <div className="flex gap-4">
                            <div style={{ flex: 1 }}>
                                <label className="text-sm">Nome Completo</label>
                                <input required className="w-full" value={name} onChange={e => setName(e.target.value)} />
                            </div>
                            <div style={{ width: '200px' }}>
                                <label className="text-sm">CPF/CNPJ</label>
                                <input required className="w-full" value={doc} onChange={e => setDoc(e.target.value)} placeholder="Apenas números" />
                            </div>
                        </div>
                        <div className="flex gap-4">
                            <div style={{ width: '150px' }}>
                                <label className="text-sm">Tipo Chave</label>
                                <select className="w-full" value={keyType} onChange={e => setKeyType(e.target.value)}>
                                    <option value="CPF">CPF</option>
                                    <option value="CNPJ">CNPJ</option>
                                    <option value="EMAIL">Email</option>
                                    <option value="PHONE">Telefone</option>
                                    <option value="EVP">Aleatória</option>
                                </select>
                            </div>
                            <div style={{ flex: 1 }}>
                                <label className="text-sm">Chave Pix</label>
                                <input required className="w-full" value={pixKey} onChange={e => setPixKey(e.target.value)} />
                            </div>
                        </div>
                        <div className="flex gap-2 justify-end">
                            <button type="button" onClick={() => setShowForm(false)} className="btn btn-outline" disabled={saving}>Cancelar</button>
                            <button type="submit" className="btn btn-primary" disabled={saving}>
                                {saving ? (
                                    <>
                                        <RefreshCw size={18} className="animate-spin" />
                                        Salvando...
                                    </>
                                ) : (
                                    'Salvar na Grafeno'
                                )}
                            </button>
                        </div>
                    </form>
                </div>
            )}

            <div className="card p-0 overflow-hidden">
                {loading ? (
                    <div className="p-8 text-center">Carregando...</div>
                ) : list.length === 0 ? (
                    <div className="p-8 text-center text-muted">
                        Nenhum beneficiário encontrado na Grafeno.
                    </div>
                ) : (
                    <table>
                        <thead>
                            <tr>
                                <th>Nome</th>
                                <th>Documento</th>
                                <th>Chave Pix</th>
                                <th>Tipo</th>
                            </tr>
                        </thead>
                        <tbody>
                            {list.map(b => (
                                <tr key={b.id}>
                                    <td>
                                        <div className="flex items-center gap-2">
                                            <div className="bg-primary/20 p-2 rounded-full">
                                                <User size={16} className="text-primary" />
                                            </div>
                                            {b.name}
                                        </div>
                                    </td>
                                    <td>{b.document || '-'}</td>
                                    <td>{b.pixKey}</td>
                                    <td>
                                        <span className="badge badge-warning uppercase">{b.keyType}</span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
};

export default Beneficiaries;
