import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getProjectDetails, runRiskAssessment, getCompliance, assessCompliance, getRiskHistory, getComplianceHistory, getTrends, getEarlyWarnings, getProjectedCompletion, getComparison, getReviews, postReview } from '../lib/api';
import { TrendingUp, BellRing, CalendarClock, Users, CheckCircle, MessageSquare, History, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';
import { TrendChart } from '../components/TrendChart';
import { RiskBadge } from '../components/RiskBadge';
import { ProvenanceBadge } from '../components/ProvenanceBadge';
import { AlertTriangle, ShieldCheck, Activity } from 'lucide-react';

export const ProjectIntelligence = () => {
  const { id } = useParams();
  const [project, setProject] = useState<any>(null);
  const [assessment, setAssessment] = useState<any>(null);
  const [compliance, setCompliance] = useState<any>(null);
  const [historyResponse, setHistoryResponse] = useState<any>(null);
  const [complianceHistory, setComplianceHistory] = useState<any>(null);
  const [trends, setTrends] = useState<any[]>([]);
  const [warnings, setWarnings] = useState<any>(null);
  const [projectedCompletion, setProjectedCompletion] = useState<any>(null);
  const [comparison, setComparison] = useState<any>(null);
  const [reviews, setReviews] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [reviewForm, setReviewForm] = useState({ reviewed_by: 'Authorized Official', action: 'COMMENT', comment: '' });
  const [submittingReview, setSubmittingReview] = useState(false);

  useEffect(() => {
    if (id) {
      getProjectDetails(Number(id)).then(setProject);
      getCompliance(Number(id)).then(setCompliance).catch(console.error);
      getRiskHistory(Number(id)).then((res) => {
        setHistoryResponse(res);
        if (res && res.assessments && res.assessments.length > 0 && !assessment) {
          const latest = res.assessments[0];
          setAssessment({
            score: latest.risk_score,
            level: latest.risk_level,
            assessment_coverage: latest.assessment_coverage,
            risk_reasons: latest.risk_reasons || []
          });
        }
      }).catch(() => setHistoryResponse(null));
      getComplianceHistory(Number(id)).then(setComplianceHistory).catch(console.error);
      getTrends(Number(id)).then(setTrends).catch(() => setTrends([]));
      getEarlyWarnings(Number(id)).then(setWarnings).catch(console.error);
      getProjectedCompletion(Number(id)).then(setProjectedCompletion).catch(console.error);
      getComparison(Number(id)).then(setComparison).catch(console.error);
      getReviews(Number(id)).then(setReviews).catch(console.error);
    }
  }, [id]);

  const handleReviewSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !reviewForm.comment) return;
    setSubmittingReview(true);
    try {
      await postReview(Number(id), reviewForm);
      setReviewForm({ ...reviewForm, comment: '' });
      getReviews(Number(id)).then(setReviews);
      // Reload project details to reflect status change
      getProjectDetails(Number(id)).then(setProject);
    } catch (err) {
      console.error(err);
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleRunAssessment = async () => {
    setLoading(true);
    try {
      const res = await runRiskAssessment(Number(id));
      setAssessment(res);
      // Refresh project to get latest risk saved in DB
      getProjectDetails(Number(id)).then(setProject);
      getRiskHistory(Number(id)).then(setHistoryResponse).catch(() => setHistoryResponse(null));
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const handleRunCompliance = async () => {
    setLoading(true);
    try {
      const res = await assessCompliance(Number(id));
      setCompliance(res);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const handleRunEarlyWarnings = async () => {
    setLoading(true);
    try {
      // Need to import assessEarlyWarnings from api at the top
      const { assessEarlyWarnings } = await import('../lib/api');
      const res = await assessEarlyWarnings(Number(id));
      setWarnings(res);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  if (!project) return <div className="p-8">Loading project...</div>;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div>
          <Link to="/projects" className="text-indigo-600 hover:underline mb-2 inline-block text-sm">← Back to Official Register</Link>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl md:text-3xl font-bold text-gray-900">
              {project.category || 'Official MPLADS Work'}
            </h1>
            <span className="bg-emerald-100 text-emerald-800 text-xs font-semibold px-3 py-1 rounded-full border border-emerald-300 flex items-center gap-1 shadow-xs">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              OFFICIAL eSAKSHI WORK #{project.work_id || project.id}
            </span>
          </div>
          <p className="text-gray-600 text-sm mt-1">
            Hon'ble MP: <span className="font-semibold text-gray-900">{project.mp_name || 'MP Allocation Linked'}</span> • District / Constituency: <span className="font-semibold text-gray-900">{project.district || project.location || 'Not available in official dataset'}</span>
          </p>
        </div>
        <div className="flex flex-col space-y-2">
          <div className="flex space-x-2 justify-end">
            <button 
              onClick={() => window.print()}
              className="bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 px-4 py-2 rounded-md font-medium shadow-sm transition"
            >
              Export Report
            </button>
          </div>
          <div className="flex space-x-2">
            <button 
              onClick={handleRunEarlyWarnings}
              disabled={loading}
              className="bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 rounded-md font-medium shadow-sm transition disabled:opacity-50 text-sm"
            >
              Assess Early Warnings
            </button>
            <button 
              onClick={handleRunCompliance}
              disabled={loading}
              className="bg-slate-800 hover:bg-slate-900 text-white px-4 py-2 rounded-md font-medium shadow-sm transition disabled:opacity-50 text-sm"
            >
              Refresh Compliance
            </button>
            <button 
              onClick={handleRunAssessment}
              disabled={loading}
              className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-md font-medium shadow-sm transition disabled:opacity-50 text-sm"
            >
              Run Risk Analysis
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Early Warning Intelligence */}
          {warnings && warnings.warnings && warnings.warnings.length > 0 && (
            <div className="bg-red-50 p-6 rounded-lg border border-red-200 shadow-sm">
              <div className="flex justify-between items-start mb-4">
                <h2 className="text-xl font-bold text-red-900 flex items-center">
                  <AlertTriangle className="mr-2 h-6 w-6 text-red-600" />
                  Early Warning Intelligence
                </h2>
                <span className="text-xs bg-red-100 text-red-800 px-2 py-1 rounded border border-red-200 font-bold uppercase">
                  Action Required
                </span>
              </div>
              <div className="space-y-4">
                {warnings.warnings.map((w: any) => (
                  <div key={w.id} className="bg-white p-4 rounded border border-red-100 shadow-sm">
                    <div className="flex justify-between items-center mb-2">
                      <span className={`text-xs font-bold px-2 py-1 rounded uppercase ${
                        w.warning_level === 'CRITICAL' ? 'bg-red-600 text-white' :
                        w.warning_level === 'HIGH' ? 'bg-orange-500 text-white' :
                        w.warning_level === 'MEDIUM' ? 'bg-amber-400 text-gray-900' :
                        'bg-blue-100 text-blue-800'
                      }`}>
                        {w.warning_level}
                      </span>
                      <span className="text-xs font-mono text-gray-500">ID: {w.id}</span>
                    </div>
                    <h3 className="font-bold text-gray-900">{w.title || w.warning_type.replace(/_/g, ' ')}</h3>
                    <p className="text-sm text-gray-700 mt-1">{w.explanation}</p>
                    
                    <div className="mt-3 flex gap-2 flex-wrap text-xs">
                      <span className="bg-gray-100 text-gray-600 px-2 py-1 rounded">
                        Status: <span className="font-bold">{w.status}</span>
                      </span>
                      {w.assessment_coverage && (
                        <span className="bg-gray-100 text-gray-600 px-2 py-1 rounded">
                          Coverage: <span className="font-bold">{w.assessment_coverage.toFixed(1)}%</span>
                        </span>
                      )}
                      <ProvenanceBadge type={w.provenance || 'AI ASSESSMENT'} />
                    </div>
                    
                    <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-500">
                      Recommendation: Review supporting project evidence. "AI FLAGS. OFFICIALS DECIDE."
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Risk Card */}
          {assessment ? (
            <div className={`p-6 rounded-lg border shadow-sm ${
              assessment.level === 'HIGH' || assessment.level === 'CRITICAL' ? 'bg-red-50 border-red-200' : 
              assessment.level === 'MEDIUM' ? 'bg-yellow-50 border-yellow-200' : 
              assessment.level === 'LIMITED' ? 'bg-gray-50 border-gray-200' :
              'bg-green-50 border-green-200'
            }`}>
              <div className="flex justify-between items-start mb-4">
                <h2 className="text-xl font-bold text-gray-900 flex items-center">
                  <Activity className="mr-2 h-6 w-6" />
                  AI Risk Signal
                </h2>
                <RiskBadge level={assessment.level} />
              </div>
              {assessment.level !== 'LIMITED' ? (
                <p className="font-semibold text-gray-800 mb-3">Score: {assessment.score}/100</p>
              ) : (
                <p className="font-semibold text-gray-600 mb-3">Score: Not Assessable</p>
              )}
              {assessment.assessment_coverage && (
                <div className="mb-4 text-xs text-gray-600 bg-white p-2 rounded border border-gray-200 inline-block shadow-sm">
                  <span className="font-semibold">Assessment Coverage: </span>
                  {assessment.assessment_coverage.assessable} of {assessment.assessment_coverage.total} indicators ({assessment.assessment_coverage.percentage}%)
                </div>
              )}
              
              <div className="mb-4 text-xs text-gray-500">
                Engine version: {assessment.engine_version || 'Unavailable'}
              </div>
              
              <div className="grid grid-cols-1 gap-4 mb-6">
                <h3 className="font-bold text-gray-800">Risk Indicator Breakdown</h3>
                {assessment.indicators && assessment.indicators.map((ind: any, idx: number) => (
                  <div key={idx} className={`p-3 rounded border ${
                    ind.severity === 'HIGH' ? 'bg-red-100 border-red-300' : 
                    ind.severity === 'MEDIUM' ? 'bg-orange-100 border-orange-300' : 
                    ind.status === 'NOT_ASSESSABLE' ? 'bg-gray-100 border-gray-300 opacity-80' :
                    'bg-white border-gray-200'
                  }`}>
                    <div className="flex justify-between items-center mb-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-gray-900 text-sm">{ind.indicator || 'Unknown Indicator'}</span>
                        {ind.confidence !== null && ind.confidence !== undefined && (
                          <span className="text-[10px] text-gray-500 font-medium">({(ind.confidence * 100).toFixed(0)}% conf)</span>
                        )}
                      </div>
                      <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                        ind.severity === 'HIGH' ? 'bg-red-200 text-red-800' : 
                        ind.severity === 'MEDIUM' ? 'bg-orange-200 text-orange-800' : 
                        ind.status === 'NOT_ASSESSABLE' ? 'bg-gray-200 text-gray-600' :
                        'bg-green-100 text-green-700'
                      }`}>{ind.status === 'NOT_ASSESSABLE' ? 'N/A' : (ind.severity || 'NORMAL')}</span>
                    </div>
                    <p className={`text-sm ${ind.status === 'NOT_ASSESSABLE' ? 'text-gray-500 italic' : 'text-gray-700'}`}>{ind.explanation || 'No explanation provided.'}</p>
                    <div className="mt-2 flex justify-between items-end">
                      {ind.data_provenance && (
                         <ProvenanceBadge type={ind.data_provenance} />
                      )}
                      {ind.score !== null && ind.score !== undefined && ind.status !== 'NOT_ASSESSABLE' && (
                        <span className="text-[10px] font-mono text-gray-500">Weight: {ind.score}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              
              <div className="mt-4">
                <h3 className="font-bold text-gray-800 mb-2">SUMMARY:</h3>
                {assessment.risk_reasons && assessment.risk_reasons.length > 0 ? (
                  <ul className="list-disc pl-5 space-y-1 text-gray-700">
                    {assessment.risk_reasons.map((r: string, idx: number) => <li key={idx}>{r}</li>)}
                  </ul>
                ) : (
                  <p className="text-gray-700 flex items-center"><ShieldCheck className="h-5 w-5 text-green-600 mr-2" /> No anomalous patterns detected.</p>
                )}
              </div>
            </div>
          ) : (
            <div className="p-12 text-center bg-gray-50 border border-gray-200 rounded-lg">
              <AlertTriangle className="mx-auto h-12 w-12 text-gray-400 mb-4" />
              <h3 className="text-lg font-medium text-gray-900">No Risk Assessment Available</h3>
              <p className="text-gray-500 mt-2">Click "Run Risk Analysis" to process this project through the AI engine.</p>
            </div>
          )}

          {/* Details Card */}
          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-bold text-gray-900">Official Government Work Data</h2>
              <span className="text-xs bg-slate-100 text-slate-700 px-2.5 py-1 rounded font-medium border border-slate-200">
                eSAKSHI Portal Record
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase">Official Work Stage (MoSPI Reported)</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <p className="text-base font-bold text-indigo-900">{project.work_stage || 'Registered'}</p>
                  <ProvenanceBadge type={project.provenance?.work_stage || 'UNAVAILABLE'} />
                </div>
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase">Analytical Progress Proxy</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-base font-bold text-gray-900">{project.progress_pct ?? 0}%</span>
                  <ProvenanceBadge type={project.provenance?.physical_progress || 'UNAVAILABLE'} />
                </div>
                <p className="text-[10px] text-gray-500 mt-1 italic">
                  Government source reports discrete stage categories, not continuous 0-100% telemetry.
                </p>
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase">Official Sanctioned Amount</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <p className="text-base font-bold text-gray-900 font-mono">
                    {project.sanctioned_amount ? `₹${Number(project.sanctioned_amount).toLocaleString('en-IN')}` : '₹0'}
                  </p>
                  <ProvenanceBadge type={project.provenance?.sanctioned_amount || 'UNAVAILABLE'} />
                </div>
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase">Actual Expenditure Reported</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <p className="text-base font-bold text-gray-900 font-mono">
                    {project.expenditure > 0 ? `₹${Number(project.expenditure).toLocaleString('en-IN')}` : 'Not yet reported in eSAKSHI sample'}
                  </p>
                  <ProvenanceBadge type={project.provenance?.expenditure || 'UNAVAILABLE'} />
                </div>
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase">Sanction / Planned Start Date</p>
                <p className="text-sm font-medium text-gray-800 mt-0.5">{project.planned_start || 'Not Recorded'}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase">Planned / Actual Completion</p>
                <p className="text-sm font-medium text-gray-800 mt-0.5">{project.actual_completion || project.planned_completion || 'Under Execution'}</p>
              </div>
            </div>
          </div>
          
          {/* Location Card */}
          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm mt-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-bold text-gray-900 flex items-center">
                <Activity className="mr-2 h-5 w-5 text-indigo-600" />
                LOCATION
              </h2>
            </div>
            {project.gps_provenance === 'UNAVAILABLE' ? (
              <div className="text-sm text-gray-700">
                <p className="font-semibold text-gray-900 mb-1">GPS: UNAVAILABLE</p>
                <p>The official dataset does not provide coordinates for this work.</p>
                <p className="mt-2 italic text-gray-500">[No location fabricated]</p>
              </div>
            ) : project.gps_provenance === 'OFFICIAL' ? (
              <div className="text-sm text-gray-700">
                <p><span className="font-semibold">Latitude:</span> {project.latitude}</p>
                <p><span className="font-semibold">Longitude:</span> {project.longitude}</p>
                <p className="font-semibold text-gray-900 mt-2">GPS: OFFICIAL</p>
                <button className="mt-3 text-indigo-600 hover:text-indigo-800 font-medium">[View on Map]</button>
              </div>
            ) : (
              <div className="text-sm text-gray-700">
                <p className="font-semibold text-gray-900 mb-1">GPS: {project.gps_provenance}</p>
                <p>Coordinates obtained through analytical/external geocoding.</p>
                <p>Not official source GPS.</p>
              </div>
            )}
          </div>
          

          {/* Compliance Card */}
          {compliance ? (
            <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm mt-6">
              <div className="flex justify-between items-start mb-6">
                <div>
                  <h2 className="text-lg font-bold text-gray-900 flex items-center">
                    <ShieldCheck className="mr-2 h-5 w-5 text-indigo-600" />
                    Compliance Intelligence
                  </h2>
                  <p className="text-xs text-gray-500 mt-1">Engine v{compliance.engine_version}</p>
                </div>
                <div className="flex flex-col items-end">
                  <span className={`px-3 py-1 rounded-full text-sm font-bold mb-2 shadow-sm border ${
                    compliance.overall_status === 'PASS' ? 'bg-green-100 text-green-800 border-green-200' :
                    compliance.overall_status === 'PASS WITH LIMITED COVERAGE' ? 'bg-green-50 text-green-700 border-green-200' :
                    compliance.overall_status === 'REVIEW' ? 'bg-yellow-100 text-yellow-800 border-yellow-200' :
                    compliance.overall_status === 'NOT_ASSESSABLE' ? 'bg-gray-100 text-gray-700 border-gray-200' :
                    'bg-red-100 text-red-800 border-red-200'
                  }`}>
                    {compliance.overall_status || 'UNKNOWN'}
                  </span>
                  <div className="text-xs font-semibold text-gray-600 bg-gray-50 px-2 py-1 rounded border border-gray-200">
                    Coverage: {compliance.coverage_percentage}%
                  </div>
                </div>
              </div>

              {/* Compliance Summary Counts */}
              <div className="grid grid-cols-4 gap-2 mb-6">
                <div className="bg-green-50 p-2 rounded border border-green-100 text-center">
                  <p className="text-xs text-green-700 font-semibold uppercase">Pass</p>
                  <p className="text-xl font-bold text-green-800">{compliance.pass_count}</p>
                </div>
                <div className="bg-yellow-50 p-2 rounded border border-yellow-100 text-center">
                  <p className="text-xs text-yellow-700 font-semibold uppercase">Review</p>
                  <p className="text-xl font-bold text-yellow-800">{compliance.review_count}</p>
                </div>
                <div className="bg-gray-50 p-2 rounded border border-gray-200 text-center opacity-80">
                  <p className="text-xs text-gray-600 font-semibold uppercase">N/A</p>
                  <p className="text-xl font-bold text-gray-700">{compliance.not_assessable_count}</p>
                </div>
                <div className={`p-2 rounded border text-center ${compliance.fail_count > 0 ? 'bg-red-50 border-red-200' : 'bg-gray-50 border-gray-100 opacity-50'}`}>
                  <p className={`text-xs font-semibold uppercase ${compliance.fail_count > 0 ? 'text-red-700' : 'text-gray-500'}`}>Fail</p>
                  <p className={`text-xl font-bold ${compliance.fail_count > 0 ? 'text-red-800' : 'text-gray-400'}`}>{compliance.fail_count}</p>
                </div>
              </div>

              <div className="space-y-6">
                {/* Grouped Checks */}
                {[
                  { title: "DATA INTEGRITY", checks: compliance.checks.filter((c: any) => ['work_id_present', 'mp_info_present', 'state_district_present', 'category_present', 'sanction_amount_valid', 'work_stage_recognized', 'sanction_date_present'].includes(c.check_id)) },
                  { title: "FINANCIAL", checks: compliance.checks.filter((c: any) => ['financial_discipline'].includes(c.check_id)) },
                  { title: "IMPLEMENTATION MONITORING", checks: compliance.checks.filter((c: any) => ['stage_duration_review'].includes(c.check_id)) },
                  { title: "UNAVAILABLE DATA", checks: compliance.checks.filter((c: any) => ['contractor_verification', 'gps_verification', 'physical_progress_verification'].includes(c.check_id)) },
                ].map((group, gIdx) => group.checks.length > 0 && (
                  <div key={gIdx} className="mb-4">
                    <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 border-b pb-1">{group.title}</h3>
                    <div className="space-y-3">
                      {group.checks.map((check: any, idx: number) => (
                        <div key={idx} className={`p-3 rounded border shadow-sm ${
                          check.status === 'PASS' ? 'bg-white border-green-200' :
                          check.status === 'REVIEW' ? 'bg-yellow-50 border-yellow-300' :
                          check.status === 'FAIL' ? 'bg-red-50 border-red-300' :
                          'bg-gray-50 border-gray-200 opacity-80'
                        }`}>
                          <div className="flex justify-between items-start mb-2">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-bold text-gray-900 text-sm">{check.check_name}</span>
                              <span className="text-[10px] font-mono text-indigo-600 bg-indigo-50 border border-indigo-100 px-1.5 py-0.5 rounded">
                                {check.rule_type}
                              </span>
                              {check.severity !== 'NOT_AVAILABLE' && check.severity !== 'NONE' && (
                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                                  check.severity === 'HIGH' ? 'bg-red-100 text-red-800' :
                                  check.severity === 'MEDIUM' ? 'bg-orange-100 text-orange-800' :
                                  'bg-yellow-100 text-yellow-800'
                                }`}>
                                  {check.severity}
                                </span>
                              )}
                            </div>
                            <div className="ml-2">
                               {check.status === 'PASS' ? <CheckCircle className="h-4 w-4 text-green-500" /> :
                                check.status === 'REVIEW' ? <AlertTriangle className="h-4 w-4 text-yellow-500" /> :
                                check.status === 'FAIL' ? <AlertTriangle className="h-4 w-4 text-red-500" /> :
                                <span className="text-xs font-bold text-gray-400">N/A</span>}
                            </div>
                          </div>
                          
                          <p className={`text-sm mb-3 ${check.status === 'NOT_ASSESSABLE' ? 'text-gray-500 italic' : 'text-gray-700'}`}>
                            {check.explanation}
                          </p>
                          
                          <div className="flex justify-between items-end border-t border-gray-100 pt-2 mt-2">
                            <ProvenanceBadge type={check.provenance} />
                            
                            {check.evidence && Object.keys(check.evidence).length > 0 && (
                              <div className="text-[10px] text-gray-500 font-mono text-right max-w-[60%] truncate">
                                {Object.entries(check.evidence)
                                  .filter(([k]) => k !== 'note')
                                  .map(([k, v]) => `${k}:${v}`)
                                  .join(' | ')}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm mt-6 text-center">
              <p className="text-sm text-gray-500 italic">Compliance data unavailable.</p>
            </div>
          )}
          
          {/* Trend Analytics Card */}
          {trends && trends.length > 0 && (
            <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm mt-6">
              <h2 className="text-lg font-bold text-gray-900 flex items-center mb-4">
                <TrendingUp className="mr-2 h-5 w-5 text-indigo-600" />
                Trend Analytics
              </h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {trends.map((t: any, idx: number) => (
                  <TrendChart 
                    key={idx} 
                    title={t.type === 'expenditure' ? 'Financial Expenditure Trend' : 'Physical Progress Trend (%)'} 
                    data={t.data} 
                    color={t.type === 'expenditure' ? '#4f46e5' : '#10b981'} 
                  />
                ))}
              </div>
            </div>
          )}

          {/* Early Warning Signals Card */}
          {warnings && warnings.warnings && warnings.warnings.length > 0 && (
            <div className="bg-red-50 p-6 rounded-lg border border-red-200 shadow-sm mt-6">
              <h2 className="text-lg font-bold text-red-900 flex items-center mb-4">
                <BellRing className="mr-2 h-5 w-5 text-red-600 animate-pulse" />
                Early Warning Signals
              </h2>
              <div className="space-y-3">
                {warnings.warnings.map((w: any, idx: number) => (
                  <div key={idx} className={`p-4 rounded border flex items-start ${
                    w.warning_level === 'HIGH' || w.warning_level === 'CRITICAL' ? 'bg-white border-red-300' :
                    w.warning_level === 'MEDIUM' ? 'bg-white border-orange-300' :
                    'bg-white border-yellow-300'
                  }`}>
                    <div className="mt-1 mr-3">
                      {w.warning_level === 'CRITICAL' || w.warning_level === 'HIGH' ? <div className="h-3 w-3 rounded-full bg-red-600 shadow-sm" /> :
                       w.warning_level === 'MEDIUM' ? <div className="h-3 w-3 rounded-full bg-orange-500 shadow-sm" /> :
                       <div className="h-3 w-3 rounded-full bg-yellow-400 shadow-sm" />}
                    </div>
                    <div>
                      <p className="font-bold text-gray-900 text-sm">{w.title || w.warning_type} <span className="text-xs font-normal text-gray-500 ml-2">({w.warning_level})</span></p>
                      <p className="text-sm text-gray-700 mt-1">{w.explanation}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Projected Completion Risk */}
          {projectedCompletion ? (
            <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm mt-6">
              <div className="flex justify-between items-start mb-4">
                <h2 className="text-lg font-bold text-gray-900 flex items-center">
                  <CalendarClock className="mr-2 h-5 w-5 text-indigo-600" />
                  Projected Completion Risk
                </h2>
                <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                  projectedCompletion.risk_level === 'HIGH' ? 'bg-red-100 text-red-800' :
                  projectedCompletion.risk_level === 'MEDIUM' ? 'bg-orange-100 text-orange-800' :
                  projectedCompletion.risk_level === 'LOW' ? 'bg-green-100 text-green-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {projectedCompletion.risk_level === 'UNKNOWN' ? 'Insufficient Data' : projectedCompletion.risk_level}
                </span>
              </div>
              <div className="p-4 bg-gray-50 rounded border border-gray-200 shadow-sm">
                <p className="text-sm font-medium text-gray-700">{projectedCompletion.explanation || 'No explanation.'}</p>
                
                {projectedCompletion.risk_level !== 'UNKNOWN' && projectedCompletion.projected_date && (
                  <div className="mt-4 grid grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
                    <div>
                      <p className="text-gray-500">Projected Date</p>
                      <p className="font-semibold text-gray-900">{projectedCompletion.projected_date}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Planned Date</p>
                      <p className="font-semibold text-gray-900">{projectedCompletion.planned_date}</p>
                    </div>
                    {projectedCompletion.velocity !== null && projectedCompletion.velocity !== undefined && (
                      <div>
                        <p className="text-gray-500">Velocity</p>
                        <p className="font-semibold text-gray-900">{projectedCompletion.velocity.toFixed(2)}% / day</p>
                      </div>
                    )}
                    {projectedCompletion.delay_days > 0 && (
                      <div className="col-span-2 lg:col-span-3 border-t pt-2 mt-2">
                        <p className="text-gray-500">Projected Delay</p>
                        <p className="font-semibold text-red-600">{projectedCompletion.delay_days} days</p>
                      </div>
                    )}
                  </div>
                )}
                
                <div className="mt-4 text-xs text-gray-500 border-t pt-2 border-gray-200 flex justify-between">
                  <span>Source: {projectedCompletion.source_type || 'Unknown'}</span>
                  {projectedCompletion.risk_level !== 'UNKNOWN' && projectedCompletion.risk_score !== undefined && (
                    <span>Risk Score: {projectedCompletion.risk_score}/100</span>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm mt-6 text-center">
              <p className="text-sm text-gray-500 italic">Projected completion data unavailable.</p>
            </div>
          )}

          {/* Peer Comparison */}
          {comparison && comparison.peer_count > 0 && (
            <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm mt-6">
              <div className="flex justify-between items-start mb-4">
                <h2 className="text-lg font-bold text-gray-900 flex items-center">
                  <Users className="mr-2 h-5 w-5 text-indigo-600" />
                  Peer Comparison
                </h2>
                <span className="text-xs font-semibold text-gray-500 bg-gray-100 px-2 py-1 rounded">
                  Compared against {comparison.peer_count} '{comparison.peer_group_name}' projects
                </span>
              </div>
              
              <div className="space-y-4">
                {comparison.metrics.map((m: any, idx: number) => (
                  <div key={idx} className={`p-4 rounded border ${m.is_anomaly ? 'bg-orange-50 border-orange-200' : 'bg-gray-50 border-gray-200'}`}>
                    <h3 className="text-sm font-semibold text-gray-800 mb-2">{m.metric_name}</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs text-gray-500">This Project</p>
                        <p className={`font-bold ${m.is_anomaly ? 'text-orange-700' : 'text-gray-900'}`}>
                          {m.project_value?.toLocaleString()}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Peer Average</p>
                        <p className="font-bold text-gray-900">{m.peer_average?.toLocaleString(undefined, { maximumFractionDigits: 1 })}</p>
                      </div>
                    </div>
                    {m.difference_percentage !== null && m.difference_percentage !== undefined && (
                      <div className="mt-3 text-xs">
                        <span className={`font-semibold ${m.is_anomaly ? 'text-orange-700' : 'text-gray-600'}`}>
                          {m.difference_percentage > 0 ? '+' : ''}{m.difference_percentage.toFixed(1)}% vs peers
                        </span>
                        {m.is_anomaly && <span className="ml-2 text-orange-600 font-bold">(Statistical Outlier)</span>}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          {/* Human Review Workflow */}
          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm mt-6">
            <h2 className="text-lg font-bold text-gray-900 flex items-center mb-4">
              <CheckCircle className="mr-2 h-5 w-5 text-indigo-600" />
              Human Review Workflow
            </h2>
            
            <div className="mb-6">
              <form onSubmit={handleReviewSubmit} className="bg-gray-50 p-4 rounded border border-gray-200">
                <div className="grid grid-cols-2 gap-4 mb-3">
                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1">Reviewed By</label>
                    <input type="text" value={reviewForm.reviewed_by} onChange={e => setReviewForm({...reviewForm, reviewed_by: e.target.value})} className="w-full text-sm p-2 border border-gray-300 rounded" required />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1">Review Decision</label>
                    <select value={reviewForm.action} onChange={e => setReviewForm({...reviewForm, action: e.target.value})} className="w-full text-sm p-2 border border-gray-300 rounded">
                      <option value="COMMENT">Record Comment</option>
                      <option value="FLAG">Flag for Review</option>
                      <option value="CLEAR">Clear Alert</option>
                      <option value="HALT">Halt / Escalate</option>
                    </select>
                  </div>
                </div>
                <div className="mb-3">
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Review Notes</label>
                  <textarea value={reviewForm.comment} onChange={e => setReviewForm({...reviewForm, comment: e.target.value})} className="w-full text-sm p-2 border border-gray-300 rounded h-20" required placeholder="Enter review notes..." />
                </div>
                <button type="submit" disabled={submittingReview} className="bg-indigo-600 text-white text-sm font-semibold py-2 px-4 rounded hover:bg-indigo-700 transition disabled:opacity-50">
                  {submittingReview ? 'Submitting...' : 'Submit Review'}
                </button>
              </form>
            </div>
            
            <div className="space-y-3">
              <h3 className="text-sm font-bold text-gray-800 flex items-center">
                <MessageSquare className="mr-1 h-4 w-4" /> Audit Log
              </h3>
              {reviews.length === 0 ? (
                <p className="text-sm text-gray-500 italic">No reviews logged yet.</p>
              ) : (
                reviews.map(r => (
                  <div key={r.id} className="p-3 bg-gray-50 rounded border border-gray-100 text-sm">
                    <div className="flex justify-between items-center mb-2">
                      <span className="font-bold text-gray-900">{r.reviewed_by} <span className="text-xs text-gray-500 font-normal ml-1">(Submitted Metadata)</span></span>
                      <span className="text-xs text-gray-500">{new Date(r.created_at).toLocaleString()}</span>
                    </div>
                    {r.action !== 'COMMENT' && (
                      <div className="mb-1 text-xs font-semibold text-indigo-700">Decision: {r.action}</div>
                    )}
                    <p className="text-gray-700">{r.comment}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
            <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wide mb-3 flex items-center">
              <History className="h-4 w-4 mr-2" /> Risk Trend Snapshot
            </h3>
            {historyResponse && historyResponse.assessments && historyResponse.assessments.length > 1 ? (
              <div className="space-y-4">
                <div className={`p-4 rounded border ${
                    historyResponse.risk_trend_status === 'INCREASING' ? 'bg-red-50 border-red-200 text-red-800' :
                    historyResponse.risk_trend_status === 'DECREASING' ? 'bg-green-50 border-green-200 text-green-800' :
                    'bg-gray-50 border-gray-200 text-gray-800'
                  }`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-sm uppercase">Risk {historyResponse.risk_trend_status}</span>
                    {historyResponse.risk_trend_status === 'INCREASING' ? <ArrowUpRight className="h-5 w-5" /> : 
                     historyResponse.risk_trend_status === 'DECREASING' ? <ArrowDownRight className="h-5 w-5" /> : 
                     <Minus className="h-5 w-5" />}
                  </div>
                  <p className="text-sm font-medium">{historyResponse.risk_trend_explanation}</p>
                </div>
                
                <div className="h-48 mt-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={[...historyResponse.assessments].reverse()}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                      <XAxis 
                        dataKey="assessed_at" 
                        tickFormatter={(val: any) => val ? new Date(val).toLocaleDateString() : ''}
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 10, fill: '#6b7280' }}
                      />
                      <YAxis 
                        domain={[0, 100]} 
                        axisLine={false}
                        tickLine={false}
                        tick={{ fontSize: 10, fill: '#6b7280' }}
                        width={30}
                      />
                      <RechartsTooltip 
                        labelFormatter={(val: any) => val ? new Date(val).toLocaleDateString() : ''}
                        formatter={(value: any) => [`${value}/100`, 'Risk Score']}
                        contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '12px' }}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="risk_score" 
                        stroke="#4f46e5" 
                        strokeWidth={3}
                        dot={{ r: 4, strokeWidth: 2 }}
                        activeDot={{ r: 6 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : (
              <div className="text-center p-4 bg-gray-50 border border-gray-200 rounded text-sm text-gray-500 italic">
                <p>Historical trend unavailable.</p>
                <p className="text-xs mt-1">Need at least 2 assessments.</p>
              </div>
            )}
            
            {complianceHistory && complianceHistory.assessments && complianceHistory.assessments.length > 1 && (
               <div className="mt-6 border-t border-gray-200 pt-4">
                 <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wide mb-3 flex items-center">
                   <ShieldCheck className="h-4 w-4 mr-2 text-indigo-600" /> Compliance Trend
                 </h3>
                 <p className="text-sm text-gray-700 font-medium mb-2">{complianceHistory.trend_status}</p>
                 <p className="text-xs text-gray-500">{complianceHistory.trend_explanation}</p>
               </div>
            )}
          </div>
          
          <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
            <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <ShieldCheck className="h-4 w-4 text-emerald-600" /> Data Provenance
            </h3>
            <div className="space-y-2 text-xs text-gray-600">
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span className="text-gray-500">Source Agency:</span>
                <span className="font-semibold text-gray-900">MoSPI (Govt of India)</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span className="text-gray-500">Government Portal:</span>
                <span className="font-semibold text-indigo-600">eSAKSHI MPLADS</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span className="text-gray-500">Portal URL:</span>
                <span className="font-mono text-gray-700">mplads.mospi.gov.in</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span className="text-gray-500">Parliamentary Term:</span>
                <span className="font-semibold text-gray-900">18th Lok Sabha</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-gray-500">Record Verification:</span>
                <span className="font-semibold text-emerald-700">Authentic Official Work</span>
              </div>
            </div>
            <div className="mt-3 pt-3 border-t border-gray-200 text-[11px] text-gray-500 leading-relaxed">
              <strong>"AI FLAGS. OFFICIALS DECIDE."</strong> AI risk indicators reflect statistical anomalies and timeline analysis across authentic data. Final audit and administrative decisions rest solely with authorized authorities.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
