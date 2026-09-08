import { useEffect, useState, useMemo } from 'react';
import { getProjects } from '../lib/api';
import { Link } from 'react-router-dom';
import { 
  Search, 
  Filter, 
  ShieldCheck, 
  ChevronLeft, 
  ChevronRight, 
  Building2, 
  Clock, 
  Info, 
  ExternalLink
} from 'lucide-react';
import { ProvenanceBadge } from '../components/ProvenanceBadge';

export const ProjectRegister = () => {
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [stageFilter, setStageFilter] = useState('ALL');
  const [riskFilter, setRiskFilter] = useState('ALL');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  useEffect(() => {
    setLoading(true);
    getProjects()
      .then((data) => {
        setProjects(data || []);
      })
      .catch((err) => {
        console.error('Failed to load projects', err);
      })
      .finally(() => setLoading(false));
  }, []);

  const stages = useMemo(() => {
    const s = new Set<string>();
    projects.forEach((p) => {
      if (p.work_stage) s.add(p.work_stage);
    });
    return Array.from(s).sort();
  }, [projects]);

  const filteredProjects = useMemo(() => {
    return projects.filter((p) => {
      const q = search.toLowerCase().trim();
      const matchesSearch =
        !q ||
        (p.work_id && String(p.work_id).toLowerCase().includes(q)) ||
        (p.category && p.category.toLowerCase().includes(q)) ||
        (p.mp_name && p.mp_name.toLowerCase().includes(q)) ||
        (p.district && p.district.toLowerCase().includes(q)) ||
        (p.description && p.description.toLowerCase().includes(q));

      const matchesStage = stageFilter === 'ALL' || p.work_stage === stageFilter;
      const matchesRisk = riskFilter === 'ALL' || p.latest_risk_level === riskFilter;

      return matchesSearch && matchesStage && matchesRisk;
    });
  }, [projects, search, stageFilter, riskFilter]);

  const totalPages = Math.ceil(filteredProjects.length / pageSize) || 1;
  const paginatedProjects = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredProjects.slice(start, start + pageSize);
  }, [filteredProjects, page, pageSize]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(e.target.value);
    setPage(1);
  };

  const handleStageChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setStageFilter(e.target.value);
    setPage(1);
  };

  const handleRiskChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setRiskFilter(e.target.value);
    setPage(1);
  };

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header & Provenance Banner */}
      <div className="flex flex-col gap-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl md:text-3xl font-bold text-gray-900 tracking-tight">
                Official Project Register
              </h1>
              <span className="bg-emerald-100 text-emerald-800 text-xs font-semibold px-3 py-1 rounded-full border border-emerald-300 flex items-center gap-1 shadow-xs">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                OFFICIAL GOVERNMENT DATA
              </span>
            </div>
            <p className="text-gray-500 text-sm mt-1">
              Ministry of Statistics and Programme Implementation (MoSPI) • eSAKSHI Portal (18th Lok Sabha)
            </p>
          </div>
          <Link
            to="/"
            className="inline-flex items-center text-sm font-semibold text-indigo-600 hover:text-indigo-800 transition"
          >
            ← Back to Executive Dashboard
          </Link>
        </div>

        {/* Data Provenance & Methodology Notice */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 text-sm text-blue-900 shadow-xs">
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-blue-950">
                Official Ingestion Verified: {projects.length} Authentic eSAKSHI Work Records
              </p>
              <p className="text-xs text-blue-800 mt-0.5">
                Work-level records fetched from the official MoSPI/eSAKSHI government API.
                Physical progress is indicated as an{' '}
                <span className="font-semibold underline">Analytical Progress Proxy</span> derived from official
                WORK_STAGE categories (Sanction, Vendor Identification, Physical Inspection, Work Completed).
              </p>
            </div>
          </div>
          <div className="shrink-0 text-xs font-mono bg-blue-100/80 px-2.5 py-1.5 rounded border border-blue-200 text-blue-900">
            Source: mplads.mospi.gov.in
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-xs flex flex-col md:flex-row items-stretch md:items-center gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by Work ID, Category, MP Name, or District..."
            value={search}
            onChange={handleSearchChange}
            className="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-500" />
            <select
              value={stageFilter}
              onChange={handleStageChange}
              className="text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            >
              <option value="ALL">All Work Stages ({stages.length})</option>
              {stages.map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>
          </div>

          <div>
            <select
              value={riskFilter}
              onChange={handleRiskChange}
              className="text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            >
              <option value="ALL">All Risk Levels</option>
              <option value="LOW">LOW Risk</option>
              <option value="MEDIUM">MEDIUM Risk</option>
              <option value="HIGH">HIGH Risk</option>
              <option value="CRITICAL">CRITICAL Risk</option>
            </select>
          </div>
        </div>
      </div>

      {/* Projects Table */}
      <div className="bg-white shadow-xs border border-gray-200 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
            <thead className="bg-gray-50/80 text-gray-600 font-semibold text-xs uppercase tracking-wider">
              <tr>
                <th className="px-5 py-3.5">Work ID & Category</th>
                <th className="px-5 py-3.5">Hon'ble MP & District</th>
                <th className="px-5 py-3.5">Sanctioned Amount</th>
                <th className="px-5 py-3.5">Official Work Stage</th>
                <th className="px-5 py-3.5">Analytical Proxy %</th>
                <th className="px-5 py-3.5">AI Risk Signal</th>
                <th className="px-5 py-3.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                    <div className="inline-flex items-center gap-2">
                      <Clock className="w-5 h-5 animate-spin text-indigo-600" />
                      <span>Loading official government records...</span>
                    </div>
                  </td>
                </tr>
              ) : paginatedProjects.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                    No authentic work records match your search criteria.
                  </td>
                </tr>
              ) : (
                paginatedProjects.map((p) => {
                  const riskLevel = p.latest_risk_level || 'LOW';
                  const riskScore = p.latest_risk_score ?? 'Not Assessable';

                  return (
                    <tr key={p.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-5 py-4 max-w-xs">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-indigo-700 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded">
                            #{p.work_id || p.id}
                          </span>
                          <span className="text-xs text-gray-400">eSAKSHI</span>
                        </div>
                        <p className="font-semibold text-gray-900 mt-1 line-clamp-2" title={p.category}>
                          {p.category || 'General Public Infrastructure'}
                        </p>
                      </td>

                      <td className="px-5 py-4 whitespace-nowrap">
                        <div className="font-medium text-gray-900">{p.mp_name || 'MP Record Pending'}</div>
                        <div className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
                          <Building2 className="w-3.5 h-3.5 text-gray-400" />
                          <span>{p.district || p.location || 'Not available in official dataset'}</span>
                        </div>
                      </td>

                      <td className="px-5 py-4 whitespace-nowrap">
                        <div className="flex flex-col items-start gap-1">
                          <span className="font-semibold text-gray-900 font-mono">
                            {p.sanctioned_amount
                              ? `₹${Number(p.sanctioned_amount).toLocaleString('en-IN')}`
                              : '₹0'}
                          </span>
                          <ProvenanceBadge type={p.provenance?.sanctioned_amount || 'UNAVAILABLE'} />
                        </div>
                      </td>

                      <td className="px-5 py-4 whitespace-nowrap">
                        <div className="flex flex-col items-start gap-1">
                          <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-slate-100 text-slate-800 border border-slate-200">
                            {p.work_stage || p.status || 'Registered'}
                          </span>
                          <ProvenanceBadge type={p.provenance?.work_stage || 'UNAVAILABLE'} />
                        </div>
                      </td>

                      <td className="px-5 py-4 whitespace-nowrap">
                        <div className="flex flex-col items-start gap-1">
                          <div className="flex items-center gap-2">
                            <div className="w-16 bg-gray-200 rounded-full h-2 overflow-hidden">
                              <div
                                className={`h-2 rounded-full ${
                                  (p.progress_pct ?? 0) === 100
                                    ? 'bg-emerald-500'
                                    : (p.progress_pct ?? 0) > 40
                                    ? 'bg-blue-500'
                                    : 'bg-amber-500'
                                }`}
                                style={{ width: `${Math.min(100, Math.max(0, p.progress_pct ?? 0))}%` }}
                              />
                            </div>
                            <span className="text-xs font-semibold text-gray-700">
                              {p.progress_pct !== null && p.progress_pct !== undefined
                                ? `${p.progress_pct}%`
                                : 'Not available in official dataset'}
                            </span>
                          </div>
                          <ProvenanceBadge type={p.provenance?.physical_progress || 'UNAVAILABLE'} />
                        </div>
                      </td>

                      <td className="px-5 py-4 whitespace-nowrap">
                        <div className="flex flex-col items-start gap-1">
                          <div className="flex items-center gap-1.5">
                            <span
                              className={`px-2.5 py-0.5 text-xs font-bold rounded-full border ${
                                riskLevel === 'CRITICAL'
                                  ? 'bg-red-100 text-red-800 border-red-200'
                                  : riskLevel === 'HIGH'
                                  ? 'bg-orange-100 text-orange-800 border-orange-200'
                                  : riskLevel === 'MEDIUM'
                                  ? 'bg-amber-100 text-amber-800 border-amber-200'
                                  : 'bg-emerald-100 text-emerald-800 border-emerald-200'
                              }`}
                            >
                              {riskLevel} ({riskScore})
                            </span>
                          </div>
                          <ProvenanceBadge type={p.provenance?.risk_score || 'AI ASSESSMENT'} />
                        </div>
                      </td>

                      <td className="px-5 py-4 whitespace-nowrap text-right font-medium">
                        <Link
                          to={`/projects/${p.id}`}
                          className="inline-flex items-center gap-1 text-xs font-semibold bg-indigo-50 text-indigo-700 hover:bg-indigo-100 px-3 py-1.5 rounded-lg border border-indigo-200 transition"
                        >
                          Analyze & Review
                          <ExternalLink className="w-3 h-3" />
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="px-6 py-4 bg-gray-50/80 border-t border-gray-200 flex flex-col sm:flex-row items-center justify-between gap-3 text-sm text-gray-600">
          <div>
            Showing{' '}
            <span className="font-semibold text-gray-900">
              {filteredProjects.length === 0 ? 0 : (page - 1) * pageSize + 1}
            </span>{' '}
            to{' '}
            <span className="font-semibold text-gray-900">
              {Math.min(page * pageSize, filteredProjects.length)}
            </span>{' '}
            of <span className="font-semibold text-gray-900">{filteredProjects.length}</span> official works
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 border border-gray-300 rounded-lg text-xs font-medium text-gray-700 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
            >
              <ChevronLeft className="w-3.5 h-3.5" /> Previous
            </button>
            <span className="text-xs font-medium text-gray-700 px-2">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1.5 border border-gray-300 rounded-lg text-xs font-medium text-gray-700 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
            >
              Next <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
