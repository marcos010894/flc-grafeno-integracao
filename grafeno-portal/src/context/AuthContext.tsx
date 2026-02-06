import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../services/api';

interface User {
    uuid: string;
    email: string;
    full_name: string;
    role: string;
    pix_key?: string;
}

interface AuthContextData {
    signed: boolean;
    user: User | null;
    signIn: (token: string, refreshToken: string) => Promise<void>;
    signOut: () => void;
    loading: boolean;
}

const AuthContext = createContext<AuthContextData>({} as AuthContextData);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function loadStoragedData() {
            const storagedUser = localStorage.getItem('user');
            const storagedToken = localStorage.getItem('access_token');

            if (storagedToken && storagedUser) {
                api.defaults.headers.Authorization = `Bearer ${storagedToken}`;
                setUser(JSON.parse(storagedUser));
            }
            setLoading(false);
        }

        loadStoragedData();
    }, []);

    async function signIn(accessToken: string, refreshToken: string) {
        localStorage.setItem('access_token', accessToken);
        localStorage.setItem('refresh_token', refreshToken);

        api.defaults.headers.Authorization = `Bearer ${accessToken}`;

        try {
            const response = await api.get('/auth/me');
            setUser(response.data);
            localStorage.setItem('user', JSON.stringify(response.data));
        } catch (error) {
            console.error("Error fetching user data", error);
        }
    }

    function signOut() {
        localStorage.clear();
        setUser(null);
    }

    return (
        <AuthContext.Provider value={{ signed: !!user, user, signIn, signOut, loading }}>
            {children}
        </AuthContext.Provider>
    );
};

export function useAuth() {
    const context = useContext(AuthContext);
    return context;
}
