import React, { useState, useEffect } from 'react';
import api from '../services/api';
import { Search, Send, User } from 'lucide-react';
import type { Beneficiary } from './Beneficiaries';

const PixSend: React.FC = () => {
    const [step, setStep] = useState(1); // 1: Key, 2: Confirm
    const [loading, setLoading] = useState(false);

    // Data
    const [pixKey, setPixKey] = useState('');
    const [keyType, setKeyType] = useState('CPF');
    const [amount, setAmount] = useState('');
    const [description, setDescription] = useState('');

    // State
    const [recipient, setRecipient] = useState<any>(null);
    const [beneficiaries, setBeneficiaries] = useState<Beneficiary[]>([]);

    // Manual Input State
    const [manualMode, setManualMode] = useState(false);
    const [manualName, setManualName] = useState('');
    const [manualDoc, setManualDoc] = useState('');

    useEffect(() => {
        const loadBeneficiaries = async () => {
            try {
                const response = await api.get('/grafeno-client/beneficiaries');
                const rawList = response.data?.data?.data || response.data?.data || [];
                // Ensure array
                const items = Array.isArray(rawList) ? rawList : [];

                const mapped = items.map((item: any) => ({
                    id: item.id,
                    name: item.attributes?.name || 'Sem Nome',
                    pixKey: item.attributes?.pixDetails?.key || 'N/A',
                    keyType: item.attributes?.pixDetails?.keyType || 'bancario',
                    document: item.attributes?.documentNumber
                }));
                setBeneficiaries(mapped);
            } catch (err) {
                console.error("Erro ao carregar beneficiários", err);
            }
        };
        loadBeneficiaries();
    }, []);

    const handleLookup = async (e: React.FormEvent) => {
        e.preventDefault();

        // Grafeno Client API generally doesn't expose a "lookup" endpoint that returns full details
        // unless you are using the Payments API directly with more permissions.
        // For this portal, we will assume we need to provide the Recipient Name explicitly
        // OR rely on saved beneficiaries.

        // If user chose manual mode or we want to force it for new keys:
        setManualMode(true);
    };

    const confirmManualData = (e: React.FormEvent) => {
        e.preventDefault();
        if (!manualName || !manualDoc) {
            alert("Nome e Documento são obrigatórios");
            return;
        }
        setRecipient({
            name: manualName,
            document: manualDoc,
            bank_name: 'Banco Externo'
        });
        setStep(2);
    };

    const handleSend = async () => {
        if (!confirm(`Confirma envio de R$ ${amount} para ${recipient.name}?`)) return;

        setLoading(true);
        try {
            // Endpoint expects: 
            // { value, pix_key, pix_key_type, beneficiary_name, beneficiary_document, description }
            const payload = {
                value: Number(amount),
                pix_key: pixKey,
                pix_key_type: keyType.toLowerCase(),
                beneficiary_name: recipient.name,
                beneficiary_document: recipient.document,
                description,
                beneficiary_id: recipient.id // Send ID if available
            };

            const response = await api.post('/grafeno-client/pix/send', payload);

            if (response.data.success) {
                alert('Pix enviado com sucesso!');
                setStep(1);
                setPixKey('');
                setAmount('');
                setDescription('');
                setRecipient(null);
                setManualMode(false);
                setManualName('');
                setManualDoc('');
            } else {
                alert('Erro ao enviar: ' + (response.data.message || response.data.error || 'Erro desconhecido'));
            }
        } catch (error: any) {
            console.error(error);
            alert(error.response?.data?.detail || 'Erro ao enviar Pix');
        } finally {
            setLoading(false);
        }
    };

    const selectBeneficiary = (b: Beneficiary) => {
        setPixKey(b.pixKey);
        setKeyType(b.keyType);
        setRecipient({
            id: b.id, // Capture ID
            name: b.name,
            document: b.document || '00000000000',
            bank_name: 'Salvo'
        });
        // If we have saved beneficiary, we might want to skip lookup or pre-fill manual
        setManualName(b.name);
        setManualDoc('00000000000'); // You might need to update Beneficiary type to store doc
        setStep(2);
    };

    return (
        <div className="container" style={{ maxWidth: '600px' }}>
            <h1 className="text-2xl mb-4">Enviar Pix (Grafeno)</h1>

            {step === 1 && (
                <>
                    <div className="card mb-4">
                        {!manualMode ? (
                            <form onSubmit={handleLookup} className="flex flex-col gap-4">
                                {/* Quick select beneficiary */}
                                {beneficiaries.length > 0 && (
                                    <div style={{ paddingBottom: '1rem', borderBottom: '1px solid var(--bg-hover)' }}>
                                        <label className="text-sm text-muted mb-2 block">Selecionar Beneficiário Salvo</label>
                                        <div style={{ display: 'flex', gap: '0.5rem', overflowX: 'auto', paddingBottom: '0.5rem' }}>
                                            {beneficiaries.map(b => (
                                                <button
                                                    key={b.id}
                                                    type="button"
                                                    className="btn btn-outline text-sm"
                                                    onClick={() => selectBeneficiary(b)}
                                                >
                                                    {b.name}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                <div className="flex gap-4">
                                    <div style={{ width: '120px' }}>
                                        <label className="mb-1 block">Tipo</label>
                                        <select className="w-full" value={keyType} onChange={e => setKeyType(e.target.value)}>
                                            <option value="CPF">CPF</option>
                                            <option value="CNPJ">CNPJ</option>
                                            <option value="EMAIL">Email</option>
                                            <option value="PHONE">Tel</option>
                                            <option value="EVP">Aleatória</option>
                                        </select>
                                    </div>
                                    <div style={{ flex: 1 }}>
                                        <label className="mb-1 block">Chave</label>
                                        <input required className="w-full" value={pixKey} onChange={e => setPixKey(e.target.value)} />
                                    </div>
                                </div>

                                <button type="submit" className="btn btn-primary" disabled={loading}>
                                    <Search size={18} />
                                    Continuar
                                </button>
                            </form>
                        ) : (
                            <form onSubmit={confirmManualData} className="flex flex-col gap-4 animate-fade-in">
                                <h3 className="text-lg font-bold">Informar Dados do Destinatário</h3>
                                <div>
                                    <label className="mb-1 block">Nome Completo</label>
                                    <input required className="w-full" value={manualName} onChange={e => setManualName(e.target.value)} />
                                </div>
                                <div>
                                    <label className="mb-1 block">CPF/CNPJ Destinatário</label>
                                    <input required className="w-full" value={manualDoc} onChange={e => setManualDoc(e.target.value)} placeholder="Apenas números" />
                                </div>
                                <div className="flex gap-2">
                                    <button type="button" onClick={() => setManualMode(false)} className="btn btn-outline flex-1">Voltar</button>
                                    <button type="submit" className="btn btn-primary flex-1">Continuar</button>
                                </div>
                            </form>
                        )}
                    </div>
                </>
            )}

            {step === 2 && recipient && (
                <div className="card animate-fade-in">
                    <h3 className="text-xl mb-4 flex items-center gap-2">
                        <User size={20} className="text-primary" />
                        Dados do Destinatário
                    </h3>

                    <div className="bg-hover p-4 rounded mb-4" style={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
                        <p><strong>Nome:</strong> {recipient.name}</p>
                        <p><strong>Banco:</strong> {recipient.bank_name}</p>
                        <p><strong>Documento:</strong> {recipient.document}</p>
                        <p><strong>Chave:</strong> {pixKey}</p>
                    </div>

                    <div className="flex flex-col gap-4">
                        <div>
                            <label className="mb-1 block">Valor (R$)</label>
                            <input
                                autoFocus
                                type="number"
                                step="0.01"
                                className="w-full text-xl font-bold"
                                value={amount}
                                onChange={e => setAmount(e.target.value)}
                                placeholder="0.00"
                            />
                        </div>

                        <div>
                            <label className="mb-1 block">Descrição (Opcional)</label>
                            <input
                                className="w-full"
                                value={description}
                                onChange={e => setDescription(e.target.value)}
                                placeholder="Ex: Pagamento serviços"
                            />
                        </div>

                        <div className="flex gap-2 pt-4">
                            <button onClick={() => setStep(1)} className="btn btn-outline flex-1">Voltar</button>
                            <button onClick={handleSend} className="btn btn-primary flex-1" disabled={!amount || loading}>
                                <Send size={18} />
                                {loading ? 'Enviando...' : 'Confirmar Envio'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default PixSend;
