import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';

// Pages
import LoginPage from './pages/LoginPage';
import Dashboard from './pages/Dashboard';
import PixCharge from './pages/PixCharge';
import PixSend from './pages/PixSend';
import Statement from './pages/Statement';
import Beneficiaries from './pages/Beneficiaries';
import MyKeys from './pages/MyKeys';

import './index.css';

const PrivateRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { signed, loading } = useAuth();

  if (loading) {
    return <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Carregando...</div>;
  }

  if (!signed) {
    return <Navigate to="/login" />;
  }

  return <>{children}</>;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="charge" element={<PixCharge />} />
            <Route path="send" element={<PixSend />} />
            <Route path="statement" element={<Statement />} />
            <Route path="beneficiaries" element={<Beneficiaries />} />
            <Route path="keys" element={<MyKeys />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
