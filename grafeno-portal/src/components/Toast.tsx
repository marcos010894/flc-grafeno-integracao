import React, { useEffect } from 'react';
import { CheckCircle, AlertCircle, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info';

interface ToastProps {
    message: string;
    type: ToastType;
    onClose: () => void;
    duration?: number;
}

const Toast: React.FC<ToastProps> = ({ message, type, onClose, duration = 4000 }) => {
    useEffect(() => {
        const timer = setTimeout(() => {
            onClose();
        }, duration);
        return () => clearTimeout(timer);
    }, [onClose, duration]);

    const bgColor = type === 'success' ? 'rgba(34, 197, 94, 0.9)' :
        type === 'error' ? 'rgba(239, 68, 68, 0.9)' : 'rgba(56, 189, 248, 0.9)';

    return (
        <div
            className="animate-slide-in"
            style={{
                position: 'fixed',
                top: '20px',
                right: '20px',
                backgroundColor: bgColor,
                color: 'white',
                padding: '1rem',
                borderRadius: '8px',
                boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                zIndex: 9999,
                minWidth: '300px',
                maxWidth: '400px',
                backdropFilter: 'blur(4px)'
            }}
        >
            {type === 'success' && <CheckCircle size={24} />}
            {type === 'error' && <AlertCircle size={24} />}
            {type === 'info' && <AlertCircle size={24} />}

            <span style={{ flex: 1, fontWeight: 500 }}>{message}</span>

            <button onClick={onClose} style={{ background: 'transparent', padding: 0 }}>
                <X size={18} color="white" />
            </button>
        </div>
    );
};

export default Toast;
