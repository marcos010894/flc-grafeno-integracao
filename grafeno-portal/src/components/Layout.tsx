import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

const Layout: React.FC = () => {
    return (
        <div className="flex">
            <Sidebar />
            <main style={{
                flex: 1,
                marginLeft: '260px',
                minHeight: '100vh',
                backgroundColor: 'var(--bg-dark)'
            }}>
                <Outlet />
            </main>
        </div>
    );
};

export default Layout;
