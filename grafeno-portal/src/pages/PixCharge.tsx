import React, { useState } from 'react';
import api from '../services/api';
import { Copy, QrCode } from 'lucide-react';
import QRCode from 'react-qr-code';

const PixCharge: React.FC = () => {
    const [amount, setAmount] = useState('');
    const [payerName, setPayerName] = useState('');
    const [payerDoc, setPayerDoc] = useState('');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<any>(null);

    const validateDocument = (doc: string): boolean => {
        // Remove formatação
        const clean = doc.replace(/[^\d]/g, '');

        // Validação básica de tamanho
        if (clean.length !== 11 && clean.length !== 14) {
            return false;
        }

        // CPF (11 dígitos)
        if (clean.length === 11) {
            // Validação simplificada - verifica se não são todos iguais
            if (/^(\d)\1{10}$/.test(clean)) return false;
            return true;
        }

        // CNPJ (14 dígitos)
        if (clean.length === 14) {
            // Validação simplificada
            if (/^(\d)\1{13}$/.test(clean)) return false;
            return true;
        }

        return false;
    };

    const handleGenerate = async (e: React.FormEvent) => {
        e.preventDefault();

        // Validação do documento se fornecido
        if (payerDoc && !validateDocument(payerDoc)) {
            alert('CPF/CNPJ inválido. Verifique o número digitado.');
            return;
        }

        setLoading(true);
        try {
            const payload = {
                value: Number(amount),
                payer_name: payerName || 'Cliente',
                payer_document: payerDoc || '11144477735' // CPF padrão se não fornecido
            };

            const response = await api.post('/grafeno-client/pix/charge', null, { params: payload });

            // Debug: Log da resposta completa
            console.log('📊 Resposta da API Grafeno:', response.data);

            if (response.data && response.data.success === false) {
                const msg = response.data.error || response.data.message || 'Erro ao gerar cobrança';
                alert("Erro: " + msg);
                setLoading(false);
                return;
            }

            // Verificar se a API retornou dados mockados
            const isMockData = response.data.pix_copy_paste === 'some long emv' ||
                response.data.pix_copy_paste?.includes('some long');

            if (isMockData) {
                console.warn('⚠️ API retornou dados mockados. Verifique a configuração da conta Grafeno.');
                console.log('Resposta completa:', response.data);
            }

            setResult(response.data);
        } catch (error: any) {
            console.error("Error generating Pix", error);

            // Mensagens de erro mais detalhadas
            let errorMsg = 'Erro ao gerar cobrança';
            if (error.response?.data?.detail) {
                errorMsg = error.response.data.detail;
            } else if (error.response?.data?.message) {
                errorMsg = error.response.data.message;
            } else if (error.message) {
                errorMsg = error.message;
            }

            alert(errorMsg);
        } finally {
            setLoading(false);
        }
    };

    const copyToClipboard = () => {
        if (result?.pix_copy_paste) {
            navigator.clipboard.writeText(result.pix_copy_paste);
            alert('Código Pix copiado! Cole no app do seu banco.');
        } else {
            alert('Código Pix não disponível');
        }
    };

    return (
        <div className="container" style={{ maxWidth: '600px' }}>
            <h1 className="text-2xl mb-4">Cobrar via Pix (Grafeno)</h1>

            {!result ? (
                <div className="card">
                    <form onSubmit={handleGenerate} className="flex flex-col gap-4">
                        <div>
                            <label style={{ display: 'block', marginBottom: '0.5rem' }}>Valor a receber (R$)</label>
                            <input
                                type="number"
                                step="0.01"
                                min="0.01"
                                value={amount}
                                onChange={e => setAmount(e.target.value)}
                                className="w-full"
                                placeholder="0,00"
                                required
                            />
                        </div>

                        <h3 className="text-sm font-bold text-muted mt-2">Dados do Pagador (Opcional, mas recomendado)</h3>
                        <div className="flex gap-4">
                            <div style={{ flex: 1 }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.8rem' }}>Nome Pagador</label>
                                <input
                                    value={payerName}
                                    onChange={e => setPayerName(e.target.value)}
                                    className="w-full"
                                    placeholder="Nome Completo"
                                />
                            </div>
                            <div style={{ flex: 1 }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.8rem' }}>CPF/CNPJ</label>
                                <input
                                    value={payerDoc}
                                    onChange={e => setPayerDoc(e.target.value)}
                                    className="w-full"
                                    placeholder="Documento"
                                />
                            </div>
                        </div>

                        <button type="submit" className="btn btn-primary mt-2" disabled={loading}>
                            <QrCode size={20} />
                            {loading ? 'Gerando...' : 'Gerar QR Code'}
                        </button>
                    </form>
                </div>
            ) : (
                <div className="card text-center">
                    <div style={{ marginBottom: '1.5rem' }}>
                        <h3 className="text-xl mb-2">Cobrança Gerada com Sucesso! ✅</h3>
                        <p className="text-muted">Valor: {Number(amount).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</p>
                        {result.charge_id && (
                            <p className="text-sm text-muted mt-1">ID: {result.charge_id}</p>
                        )}
                    </div>

                    <div style={{ background: '#fff', padding: '1rem', borderRadius: '0.5rem', display: 'inline-block', marginBottom: '1.5rem' }}>
                        {result.pix_copy_paste ? (
                            <QRCode value={result.pix_copy_paste} size={200} />
                        ) : result.pix_qrcode ? (
                            <img src={`data:image/png;base64,${result.pix_qrcode}`} alt="QR Code Pix" style={{ maxWidth: '200px' }} />
                        ) : (
                            <div style={{ width: 200, height: 200, background: '#eee', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#666', fontSize: '14px', textAlign: 'center', padding: '1rem' }}>
                                QR Code não disponível.<br />Use o código Pix abaixo.
                            </div>
                        )}
                    </div>

                    {result.pix_copy_paste && (
                        <div className="flex flex-col gap-2" style={{ marginBottom: '1rem' }}>
                            <p className="text-sm font-bold">Pix Copia e Cola</p>
                            <p className="text-xs text-muted">Cole este código no app do seu banco</p>

                            {/* Aviso se for dado mockado */}
                            {(result.pix_copy_paste === 'some long emv' || result.pix_copy_paste?.includes('some long')) && (
                                <div style={{
                                    background: '#fff3cd',
                                    border: '1px solid #ffc107',
                                    padding: '0.75rem',
                                    borderRadius: '0.375rem',
                                    marginBottom: '0.5rem'
                                }}>
                                    <p style={{ fontSize: '0.75rem', color: '#856404', margin: 0 }}>
                                        ⚠️ <strong>Modo de Teste:</strong> A API Grafeno retornou dados mockados.
                                        Verifique se a conta está em modo sandbox ou se precisa de configuração adicional.
                                    </p>
                                </div>
                            )}

                            <div className="flex gap-2">
                                <input
                                    readOnly
                                    value={result.pix_copy_paste}
                                    className="w-full"
                                    style={{ fontSize: '0.7rem', fontFamily: 'monospace' }}
                                />
                                <button type="button" onClick={copyToClipboard} className="btn btn-outline">
                                    <Copy size={18} />
                                </button>
                            </div>
                        </div>
                    )}

                    {result.due_date && (
                        <p className="text-xs text-muted mb-2">
                            Vencimento: {new Date(result.due_date).toLocaleDateString('pt-BR')}
                        </p>
                    )}

                    <button onClick={() => setResult(null)} className="btn btn-outline w-full mt-4">
                        Nova Cobrança
                    </button>

                    {/* Debug info sempre visível em desenvolvimento */}
                    <details style={{ marginTop: '1rem', fontSize: '0.7rem', textAlign: 'left' }}>
                        <summary style={{ cursor: 'pointer', color: '#666' }}>Debug Info</summary>
                        <pre style={{ background: '#f5f5f5', padding: '0.5rem', borderRadius: '0.25rem', overflow: 'auto', maxHeight: '200px' }}>
                            {JSON.stringify(result, null, 2)}
                        </pre>
                    </details>
                </div>
            )}
        </div>
    );
};

export default PixCharge;
