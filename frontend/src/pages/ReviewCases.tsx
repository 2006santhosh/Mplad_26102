import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getReviewCases } from '../lib/api';
import {
  Folder, AlertTriangle, CheckCircle, Clock, XCircle,
  Filter, RefreshCw, ChevronRight, ShieldAlert
} from 'lucide-react';

const STATUS_COLORS: Record<string, string> = {
  OPEN: 'bg-blue-100 text-blue-800 border-blue-200',
  UNDER_REVIEW: 'bg-amber-100 text-amber-800 border-amber-200',
  ACTION_REQUIRED: 'bg-red-100 text-red-800 border-red-200',
  RESOLVED: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  DISMISSED: 'bg-gray-100 text-gray-600 border-gray-200',
};

const PRIORITY_COLORS: Record<string, string> = {
  CRITICAL: 'bg-red-100 text-red-800 border-red-200',
  HIGH: 'bg-orange-100 text-orange-800 border-orange-200',
  MEDIUM: 'bg-amber-100 text-amber-800 border-amber-200',
  LOW: 'bg-slate-100 text-slate-700 border-slate-200',
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  OPEN: <Folder className="w-4 h-4 text-blue-600" />,
  UNDER_REVIEW: <Clock className="w-4 h-4 text-amber-600" />,
  ACTION_REQUIRED: <AlertTriangle className="w-4 h-4 text-red-600" />,
  RESOLVED: <CheckCircle className="w-4 h-4 text-emerald-600" />,
  DISMISSED: <XCircle className="w-4 h-4 text-gray-500" />,
};

export const ReviewCases = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    status: '',
    priority: '',
    district: '',
  });

  const loadCases = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (filters.status) params.status = filters.status;
      if (filters.priority) params.priority = filters.priority;
      if (filters.district) params.district = filters.district;
      const res = await getReviewCases(params);
      setData(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCases();
  }, [filters]);

  const summaryCards = data ? [
    { label: 'Total Open', value: data.open_count, color: 'border-l-blue-500', icon: <Folder className="w-5 h-5 text-blue-500" />, status: 'OPEN' },
    { label: 'Under Review', value: data.under_review_count, color: 'border-l-amber-500', icon: <Clock className="w-5 h-5 text-amber-500" />, status: 'UNDER_REVIEW' },
    { label: 'Action Required', value: data.action_required_count, color: 'border-l-red-500', icon: <AlertTriangle className="w-5 h-5 text-red-500" />, status: 'ACTION_REQUIRED' },
    { label: 'Resolved', value: data.resolved_count, color: 'border-l-emerald-500', icon: <CheckCircle className="w-5 h-5 text-emerald-500" />, status: 'RESOLVED' },
    { label: 'Dismissed', value: data.dismissed_count, color: 'border-l-gray-400', icon: <XCircle className="w-5 h-5 text-gray-400" />, status: 'DISMISSED' },
  ] : [];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 font-sans">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-6">
        <div>
          <div className="flex items-center gap-3">
            <ShieldAlert className="w-7 h-7 text-indigo-600" />
            <h1 className="text-2xl font-bold text-gray-900">Official Review Cases</h1>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Investigation workflow — AI identifies signals, officials decide and act.
            Every action is audited.
          </p>
        </div>
        <button
          onClick={loadCases}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 shadow-sm transition"
        >
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {summaryCards.map((card) => (
          <button
            key={card.label}
            onClick={() => setFilters(f => ({ ...f, status: f.status === card.status ? '' : card.status }))}
            className={`bg-white p-4 rounded-xl border-l-4 ${card.color} border border-gray-200 shadow-sm hover:shadow-md transition text-left`}
          >
            <div className="flex items-center gap-2 mb-1">{card.icon}<span className="text-xs text-gray-500 font-medium">{card.label}</span></div>
            <div className="text-3xl font-bold text-gray-900">{card.value ?? '—'}</div>
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-3 text-sm font-semibold text-gray-700">
          <Filter className="w-4 h-4 text-gray-400" /> Filters
        </div>
        <div className="flex flex-wrap gap-3">
          <select
            value={filters.status}
            onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}
            className="border border-gray-200 rounded-md px-3 py-2 text-sm text-gray-700 bg-gray-50 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
          >
            <option value="">All Statuses</option>
            {['OPEN', 'UNDER_REVIEW', 'ACTION_REQUIRED', 'RESOLVED', 'DISMISSED'].map(s => (
              <option key={s} value={s}>{s.replace('_', ' ')}</option>
            ))}
          </select>
          <select
            value={filters.priority}
            onChange={e => setFilters(f => ({ ...f, priority: e.target.value }))}
            className="border border-gray-200 rounded-md px-3 py-2 text-sm text-gray-700 bg-gray-50 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
          >
            <option value="">All Priorities</option>
            {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(p => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Filter by district..."
            value={filters.district}
            onChange={e => setFilters(f => ({ ...f, district: e.target.value }))}
            className="border border-gray-200 rounded-md px-3 py-2 text-sm text-gray-700 bg-gray-50 focus:ring-2 focus:ring-indigo-400 focus:outline-none min-w-[200px]"
          />
          {(filters.status || filters.priority || filters.district) && (
            <button
              onClick={() => setFilters({ status: '', priority: '', district: '' })}
              className="text-xs text-indigo-600 hover:underline font-medium"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Cases Table */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b bg-gray-50/50 flex justify-between items-center">
          <h2 className="font-bold text-gray-900 text-sm">
            {loading ? 'Loading cases...' : `${data?.total ?? 0} case${(data?.total ?? 0) !== 1 ? 's' : ''} found`}
          </h2>
        </div>

        {loading ? (
          <div className="p-12 text-center text-gray-400">
            <Clock className="w-8 h-8 animate-spin mx-auto mb-3 opacity-50" />
            Loading review cases...
          </div>
        ) : !data?.cases?.length ? (
          <div className="p-12 text-center text-gray-400">
            <Folder className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p className="text-base font-medium text-gray-500">No review cases found.</p>
            <p className="text-sm text-gray-400 mt-1">
              Cases are created by authorized officials from Project Intelligence when AI signals require review.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {data.cases.map((c: any) => (
              <div
                key={c.id}
                className="px-6 py-4 hover:bg-gray-50 transition cursor-pointer flex items-center justify-between gap-4"
                onClick={() => navigate(`/review-cases/${c.id}`)}
              >
                <div className="flex items-center gap-4 min-w-0">
                  <div className="shrink-0">{STATUS_ICONS[c.status] || <Folder className="w-4 h-4" />}</div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-indigo-700 text-sm font-mono">{c.case_reference}</span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${STATUS_COLORS[c.status] || ''}`}>
                        {c.status?.replace('_', ' ')}
                      </span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${PRIORITY_COLORS[c.priority] || ''}`}>
                        {c.priority}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1 truncate max-w-xl">{c.summary || 'No summary recorded.'}</p>
                    <div className="flex gap-3 text-[11px] text-gray-400 mt-1">
                      <span>Project #{c.project_id}</span>
                      {c.opened_by && <span>Opened by: <strong className="text-gray-600">{c.opened_by.username}</strong></span>}
                      {c.assigned_to && <span>Assigned: <strong className="text-gray-600">{c.assigned_to.username}</strong></span>}
                      <span>{new Date(c.opened_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-gray-400 shrink-0" />
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4 text-sm text-indigo-700">
        <strong>Provenance note:</strong> Review cases are created by authorized officials.
        AI signals (Early Warnings, Risk Assessments) remain intact as <code className="font-mono text-xs bg-indigo-100 px-1 rounded">AI ASSESSMENT</code> records
        and are never deleted by case actions.
      </div>
    </div>
  );
};
