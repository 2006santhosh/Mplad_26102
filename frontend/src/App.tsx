import React from 'react';
import { BrowserRouter, Routes, Route, Link, Navigate, useLocation } from 'react-router-dom';
import { Dashboard } from './pages/Dashboard';
import { ProjectRegister } from './pages/ProjectRegister';
import { ProjectIntelligence } from './pages/ProjectIntelligence';
import { PreSanction } from './pages/PreSanction';
import { Login } from './pages/Login';
import { ReviewCases } from './pages/ReviewCases';
import { ReviewCaseDetail } from './pages/ReviewCaseDetail';
import { logout } from './lib/api';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('token');
  const location = useLocation();
  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return children as React.ReactElement;
};

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-100 font-sans">
        <nav className="bg-slate-900 text-white shadow-md">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16 items-center">
              <div className="flex-shrink-0 font-bold text-xl tracking-wide flex items-center">
                <span className="text-indigo-400 mr-2">🏛️</span>
                MPLAD Risk Intelligence
              </div>
              <div className="flex space-x-4">
                <Link to="/" className="px-3 py-2 rounded-md text-sm font-medium hover:bg-slate-800">Dashboard</Link>
                <Link to="/projects" className="px-3 py-2 rounded-md text-sm font-medium hover:bg-slate-800">Projects</Link>
                <Link to="/review-cases" className="px-3 py-2 rounded-md text-sm font-medium hover:bg-slate-800 text-indigo-300">Review Cases</Link>
                <Link to="/pre-sanction" className="px-3 py-2 rounded-md text-sm font-medium hover:bg-slate-800">Pre-Sanction</Link>
                {localStorage.getItem('token') && (
                  <button onClick={logout} className="px-3 py-2 rounded-md text-sm font-medium hover:bg-red-800 bg-red-900/50">Logout</button>
                )}
              </div>
            </div>
          </div>
        </nav>
        
        <main>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
              <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
              <Route path="/projects" element={<ProtectedRoute><ProjectRegister /></ProtectedRoute>} />
              <Route path="/projects/:id" element={<ProtectedRoute><ProjectIntelligence /></ProtectedRoute>} />
              <Route path="/review-cases" element={<ProtectedRoute><ReviewCases /></ProtectedRoute>} />
              <Route path="/review-cases/:id" element={<ProtectedRoute><ReviewCaseDetail /></ProtectedRoute>} />
              <Route path="/pre-sanction" element={<ProtectedRoute><PreSanction /></ProtectedRoute>} />
            </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
