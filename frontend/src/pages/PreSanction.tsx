import React, { useState, useEffect } from 'react';
import { runPreSanction, getPreSanctionHistory } from '../lib/api';
import { RiskBadge } from '../components/RiskBadge';
import { Link } from 'react-router-dom';

export const PreSanction = () => {
  const [formData, setFormData] = useState({
    category: 'Road Infrastructure',
    sanctioned_amount: '',
    location: '',
    planned_duration_days: '180'
  });
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<any[]>([]);

  const fetchHistory = async () => {
    try {
      const data = await getPreSanctionHistory();
      setHistory(data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await runPreSanction({
        ...formData,
        sanctioned_amount: Number(formData.sanctioned_amount),
        planned_duration_days: Number(formData.planned_duration_days)
      });
      setResult(res);
      fetchHistory();
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Pre-Sanction Risk Check</h1>
        <Link to="/" className="text-indigo-600 hover:underline">← Back to Dashboard</Link>
      </div>
      
      <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm mb-8">
        <p className="text-gray-600 mb-6">Enter proposed project details to compare against historical peer projects before sanctioning.</p>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
              <select 
                className="w-full border border-gray-300 rounded p-2"
                value={formData.category}
                onChange={e => setFormData({...formData, category: e.target.value})}
              >
                <option value="Road Infrastructure">Road Infrastructure</option>
                <option value="Education">Education</option>
                <option value="Water Supply">Water Supply</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Estimated Cost (₹)</label>
              <input 
                type="number" required 
                className="w-full border border-gray-300 rounded p-2"
                value={formData.sanctioned_amount}
                onChange={e => setFormData({...formData, sanctioned_amount: e.target.value})}
              />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Location / Description</label>
              <input 
                type="text" required 
                className="w-full border border-gray-300 rounded p-2"
                value={formData.location}
                onChange={e => setFormData({...formData, location: e.target.value})}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Planned Duration (Days)</label>
              <input 
                type="number" required 
                className="w-full border border-gray-300 rounded p-2"
                value={formData.planned_duration_days}
                onChange={e => setFormData({...formData, planned_duration_days: e.target.value})}
              />
            </div>
          </div>
          <div className="pt-4">
            <button 
              type="submit" disabled={loading}
              className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2 rounded-md font-medium shadow-sm transition disabled:opacity-50"
            >
              {loading ? 'Analyzing...' : 'Run Analysis'}
            </button>
          </div>
        </form>
      </div>

      {result && (
        <div className={`p-6 rounded-lg border shadow-sm mb-8 ${result.risk_level === 'HIGH' ? 'bg-red-50 border-red-200' : result.risk_level === 'MEDIUM' ? 'bg-yellow-50 border-yellow-200' : 'bg-green-50 border-green-200'}`}>
           <div className="flex justify-between items-center mb-4">
             <h2 className="text-xl font-bold text-gray-900">Analysis Result</h2>
             <RiskBadge level={result.risk_level} />
           </div>
           {result.risk_reasons && result.risk_reasons.length > 0 ? (
             <div>
                <h3 className="font-bold text-gray-800 mb-2">WARNINGS:</h3>
                <ul className="list-disc pl-5 space-y-1 text-gray-700">
                  {result.risk_reasons.map((r: string, idx: number) => <li key={idx}>{r}</li>)}
                </ul>
             </div>
           ) : (
             <p className="text-gray-700">Cost and characteristics align with historical peer projects. Low risk of anomaly.</p>
           )}
        </div>
      )}

      {history.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
            <h3 className="text-lg font-bold text-gray-900">Assessment History</h3>
          </div>
          <div className="divide-y divide-gray-200">
            {history.map((item: any) => (
              <div key={item.id} className="p-6">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <span className="text-sm font-semibold text-gray-900">{item.proposed_category}</span>
                    <span className="mx-2 text-gray-300">|</span>
                    <span className="text-sm text-gray-600">₹{item.proposed_amount?.toLocaleString('en-IN')}</span>
                  </div>
                  <RiskBadge level={item.risk_level} />
                </div>
                {item.description && <p className="text-sm text-gray-600 mb-3">{item.description}</p>}
                <div className="flex flex-wrap gap-4 text-xs text-gray-500">
                  <span>{new Date(item.assessed_at).toLocaleString()}</span>
                  <span className="font-mono bg-gray-100 px-2 py-0.5 rounded border border-gray-200 text-gray-700">
                    Provenance: {item.provenance}
                  </span>
                  {item.assessment_status && (
                    <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded border border-blue-200">
                      Status: {item.assessment_status}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
