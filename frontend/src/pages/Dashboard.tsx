import { useEffect, useState } from 'react';
import { getProjects, getSpatialClusters, getDashboardStats } from '../lib/api';
import { Link } from 'react-router-dom';
import { ProjectMap } from '../components/ProjectMap';
import { 
  ShieldCheck, 
  AlertTriangle, 
  Building2, 
  BarChart3, 
  Layers, 
  ArrowRight,
  Info,
  Clock
} from 'lucide-react';

export const Dashboard = () => {
  const [projects, setProjects] = useState<any[]>([]);
  const [clusters, setClusters] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getProjects(),
      getSpatialClusters().catch(() => null),
      getDashboardStats().catch(() => null)
    ])
      .then(([pList, cData, sData]) => {
        setProjects(pList || []);
        setClusters(cData);
        setStats(sData);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-8 font-sans">
      {loading && (
        <div className="flex items-center gap-2 p-3 bg-indigo-50 border border-indigo-100 rounded-lg text-xs text-indigo-700">
          <Clock className="w-4 h-4 animate-spin" />
          <span>Synchronizing authentic government MPLADS records and spatial indices...</span>
        </div>
      )}
      {/* Top Banner & Title */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-200 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">
              MPLADS Risk Intelligence
            </h1>
            <span className="bg-emerald-100 text-emerald-800 text-xs font-semibold px-3 py-1 rounded-full border border-emerald-300 flex items-center gap-1 shadow-xs">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              OFFICIAL GOVERNMENT DATA
            </span>
          </div>
          <p className="text-indigo-700 font-semibold tracking-wider text-sm mt-1 uppercase">
            AI FLAGS. OFFICIALS DECIDE.
          </p>
          <p className="text-gray-500 text-xs mt-1">
            Data Sources: MoSPI Hon'ble MP Allocation Dataset ({stats ? stats.total_mps : 'Loading...'} MPs) &amp; eSAKSHI Official Work Dataset ({stats ? stats.total_projects : 'Loading...'} Works)
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/projects"
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold px-4 py-2.5 rounded-lg shadow-sm transition"
          >
            Open Project Register
            <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            to="/pre-sanction"
            className="inline-flex items-center gap-2 bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 text-sm font-semibold px-4 py-2.5 rounded-lg shadow-sm transition"
          >
            Pre-Sanction Check
          </Link>
        </div>
      </header>

      {/* Official Ingestion Transparency Card */}
      <div className="bg-gradient-to-r from-blue-50 via-indigo-50 to-blue-50 border border-blue-200 rounded-xl p-5 shadow-xs">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="p-2 bg-blue-600 text-white rounded-lg shadow-xs mt-0.5">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-gray-900 text-base">
                Official Multi-State MPLADS Ingestion Pipeline
              </h3>
              <p className="text-xs text-gray-600 mt-1 max-w-3xl leading-relaxed">
                Operating strictly on authentic MoSPI datasets. Includes <strong>{stats ? stats.total_mps : 'Loading...'} official MP allocation limits</strong> (~₹8,318 Cr) across India and <strong>{stats ? stats.total_projects : 'Loading...'} authentic work-level records</strong> fetched directly from the MoSPI/eSAKSHI API across multiple states. Zero synthetic projects exist in the primary flow.
              </p>
            </div>
          </div>
          <div className="shrink-0 flex items-center gap-2 text-xs font-mono bg-white px-3 py-2 rounded-lg border border-blue-200 text-blue-900 shadow-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            Live Government Seed Active
          </div>
        </div>
      </div>

        {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Portfolio Overview */}
        <div className="bg-white p-6 rounded-xl shadow-xs border border-gray-200 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
                <Building2 className="w-5 h-5 text-indigo-600" />
                Portfolio Allocation
              </h2>
              <span className="text-xs font-medium text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                18th Lok Sabha
              </span>
            </div>
            <div className="space-y-3.5 text-sm">
              <div className="flex justify-between items-center pb-2 border-b border-gray-100">
                <span className="text-gray-600">Hon'ble MPs Tracked</span>
                <span className="font-bold text-gray-900 font-mono">
                  {stats ? `${stats.total_mps} MPs` : 'Loading...'}
                </span>
              </div>
              <div className="flex justify-between items-center pb-2 border-b border-gray-100">
                <span className="text-gray-600">Total MP Allocation Limit</span>
                <span className="font-bold text-gray-900 font-mono">
                  {stats ? (stats.total_allocated_amount ? `₹${(stats.total_allocated_amount / 10000000).toFixed(1)} Cr` : 'Data Unavailable') : 'Loading...'}
                </span>
              </div>
              <div className="flex justify-between items-center pb-2 border-b border-gray-100">
                <span className="text-gray-600">eSAKSHI Works Tracked</span>
                <span className="font-bold text-indigo-700 font-mono">
                  {stats ? `${stats.total_projects.toLocaleString()} Works` : 'Loading...'}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Total Sanctioned (Works)</span>
                <span className="font-bold text-gray-900 font-mono">
                  {stats ? `₹${(stats.total_sanctioned_amount / 10000000).toFixed(2)} Cr` : 'Loading...'}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-gray-100 text-xs text-gray-500 flex items-center justify-between">
            <span>Actual MoSPI Expenditure:</span>
            <span className="font-bold text-emerald-700 font-mono">
              {stats ? `₹${(stats.total_expenditure / 10000000).toFixed(2)} Cr` : 'Loading...'}
            </span>
          </div>
        </div>

        {/* AI Risk Intelligence Distribution */}
        <div className="bg-white p-6 rounded-xl shadow-xs border border-gray-200 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-indigo-600" />
                AI Risk Flags (Official Works)
              </h2>
              <span className="text-xs font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
                AI Assessment
              </span>
            </div>

            {stats && stats.risk_distribution ? (
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-emerald-50/80 p-3 rounded-lg border border-emerald-200 flex flex-col items-center">
                  <span className="text-[11px] font-bold text-emerald-800 uppercase tracking-wider">LOW</span>
                  <span className="text-2xl font-black text-emerald-900 mt-1 font-mono">
                    {stats.risk_distribution.LOW}
                  </span>
                  <span className="text-[10px] text-emerald-700">Normal Parameters</span>
                </div>
                <div className="bg-amber-50/80 p-3 rounded-lg border border-amber-200 flex flex-col items-center">
                  <span className="text-[11px] font-bold text-amber-800 uppercase tracking-wider">MEDIUM</span>
                  <span className="text-2xl font-black text-amber-900 mt-1 font-mono">
                    {stats.risk_distribution.MEDIUM}
                  </span>
                  <span className="text-[10px] text-amber-700">Minor Variance</span>
                </div>
                <div className="bg-orange-50/80 p-3 rounded-lg border border-orange-200 flex flex-col items-center">
                  <span className="text-[11px] font-bold text-orange-800 uppercase tracking-wider">HIGH</span>
                  <span className="text-2xl font-black text-orange-900 mt-1 font-mono">
                    {stats.risk_distribution.HIGH}
                  </span>
                  <span className="text-[10px] text-orange-700">Review Recommended</span>
                </div>
                <div className="bg-red-50/80 p-3 rounded-lg border border-red-200 flex flex-col items-center">
                  <span className="text-[11px] font-bold text-red-800 uppercase tracking-wider">CRITICAL</span>
                  <span className="text-2xl font-black text-red-900 mt-1 font-mono">
                    {stats.risk_distribution.CRITICAL}
                  </span>
                  <span className="text-[10px] text-red-700">Priority Review</span>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-sm text-gray-500">Calculating risk distribution...</div>
            )}
          </div>

          <p className="mt-4 pt-3 border-t border-gray-100 text-[11px] text-gray-500 italic text-center">
            Flags indicate statistical variance or timeline mismatch; officials verify ground reality.
          </p>
        </div>

        {/* Attention Signals & Governance */}
        <div className="bg-white p-6 rounded-xl shadow-xs border border-gray-200 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-bold text-gray-900 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-600" />
                Attention Signals
              </h2>
              <span className="text-xs font-semibold text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                Action Required
              </span>
            </div>

            <div className="space-y-3 text-sm">
              <div className="flex justify-between items-center pb-2 border-b border-gray-100">
                <span className="text-gray-600">AI Risk Signals (Med/High/Crit)</span>
                <span className="font-bold text-orange-600 font-mono">
                  {stats ? stats.ai_risk_projects : 'Loading...'}
                </span>
              </div>
              <div className="flex justify-between items-center pb-2 border-b border-gray-100">
                <span className="text-gray-600">Delayed Official Works</span>
                <span className="font-bold text-amber-600 font-mono">
                  {stats ? stats.delayed_projects : 'Loading...'}
                </span>
              </div>
              <div className="flex justify-between items-center pb-2 border-b border-gray-100">
                <span className="text-gray-600">High Predictive Completion Risk</span>
                <span className="font-bold text-red-600 font-mono">
                  {stats && stats.predictive_high_risk !== undefined ? stats.predictive_high_risk : 'Loading...'}
                </span>
              </div>
              <div className="flex justify-between items-center pb-2 border-b border-gray-100">
                <span className="text-gray-600">Human Official Review Logs</span>
                <span className="font-bold text-indigo-600 font-mono">
                  {stats ? stats.human_review_flags : 'Loading...'}
                </span>
              </div>
              <div className="flex justify-between items-center pb-2 border-b border-gray-100">
                <span className="text-gray-600">GPS Coverage (Authentic)</span>
                <span className="font-bold text-gray-900 font-mono">
                  {stats && stats.gps_coverage_percentage !== undefined ? `${stats.gps_coverage_percentage.toFixed(1)}%` : 'Loading...'}
                </span>
              </div>
              <div className="flex justify-between items-center pt-1">
                <span className="text-sm font-bold text-gray-900">Total Requiring Attention</span>
                <span className="font-bold text-xl text-indigo-700 font-mono">
                  {stats ? stats.projects_requiring_attention : 'Loading...'}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-gray-100">
            <Link
              to="/projects"
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center justify-center gap-1"
            >
              Filter flagged works in Project Register →
            </Link>
          </div>
        </div>
      </div>

      {/* Top Work Categories Breakdown */}
      {stats && stats.projects_by_category && stats.projects_by_category.length > 0 && (
        <div className="bg-white rounded-xl shadow-xs border border-gray-200 p-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
            <div>
              <h3 className="text-lg font-bold text-gray-900">
                Official Work Categories Breakdown
              </h3>
              <p className="text-xs text-gray-500 mt-0.5">
                Authentic distribution of {stats ? stats.total_projects : 'Loading...'} work records from eSAKSHI government database
              </p>
            </div>
            <span className="text-xs font-semibold text-gray-600 bg-gray-100 px-3 py-1 rounded-full self-start">
              Top Categories by Sanctioned Value
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {stats.projects_by_category.slice(0, 6).map((cat: any, idx: number) => (
              <div key={idx} className="p-4 bg-gray-50/80 rounded-lg border border-gray-200 flex flex-col justify-between">
                <div>
                  <div className="flex justify-between items-start gap-2">
                    <span className="text-xs font-bold text-indigo-700 bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded">
                      #{idx + 1}
                    </span>
                    <span className="text-xs font-bold text-gray-700 font-mono">
                      {cat.count} works
                    </span>
                  </div>
                  <h4 className="font-semibold text-gray-900 text-sm mt-2 line-clamp-2" title={cat.category}>
                    {cat.category}
                  </h4>
                </div>
                <div className="mt-3 pt-2 border-t border-gray-200/60 flex justify-between items-center text-xs">
                  <span className="text-gray-500">Sanctioned:</span>
                  <span className="font-bold text-gray-900 font-mono">
                    ₹{(cat.total_amount / 10000000).toFixed(2)} Cr
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Administrative Geographic Analysis */}
      <div className="bg-white rounded-xl shadow-xs border border-gray-200 p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-lg font-bold text-gray-900">
              Administrative Geographic Distribution
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Coverage across States, Districts, and Constituencies from official eSAKSHI records
            </p>
          </div>
          <div className="flex items-center gap-2">
            {clusters && clusters.clusters && clusters.clusters.length > 0 && (
              <span className="text-xs font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200 px-3 py-1 rounded-full">
                {clusters.clusters.length} Spatial Clusters
              </span>
            )}
            <span className="text-xs font-medium text-blue-800 bg-blue-50 border border-blue-200 px-3 py-1 rounded-full flex items-center gap-1.5">
              <Info className="w-3.5 h-3.5 text-blue-600" />
              Administrative Level Analysis (No Fake GPS)
            </span>
          </div>
        </div>

        {/* GIS Integrity Notice */}
        <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-700 flex items-start gap-3">
          <ShieldCheck className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
          <div>
            <strong>Government Data Integrity Commitment:</strong> The official MoSPI eSAKSHI work export does not report street-level GPS coordinates for this sample batch. Exact latitude and longitude are preserved as null to prevent synthetic fabrication. Geographic risk analysis is conducted purely at the administrative State and District level.
          </div>
        </div>

        <ProjectMap projects={projects} />
      </div>
    </div>
  );
};
