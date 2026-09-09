import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { getProjectDetails, getDecisionSupport, getReviews, postReview, getProjectReviewCases, createReviewCase } from '../lib/api';
import { 
  ShieldCheck, AlertTriangle, AlertCircle, Clock, CheckCircle, 
  History, Info, MessageSquare, Server, Layers, FolderOpen, ExternalLink
} from 'lucide-react';
import { ProvenanceBadge } from '../components/ProvenanceBadge';

export const ProjectIntelligence = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState<any>(null);
  const [decisionSupport, setDecisionSupport] = useState<any>(null);
  const [reviews, setReviews] = useState<any[]>([]);
  const [projectCases, setProjectCases] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCaseDialog, setShowCaseDialog] = useState(false);
  const [caseNote, setCaseNote] = useState('');
  const [creatingCase, setCreatingCase] = useState(false);
  
  const [reviewForm, setReviewForm] = useState({ reviewed_by: 'Authorized Official', action: 'COMMENT', comment: '' });
  const [submittingReview, setSubmittingReview] = useState(false);

  useEffect(() => {
    if (id) {
      const numId = Number(id);
      setLoading(true);
      Promise.all([
        getProjectDetails(numId).then(setProject),
        getDecisionSupport(numId).then(setDecisionSupport),
        getReviews(numId).then(setReviews).catch(() => {}),
        getProjectReviewCases(numId).then(setProjectCases).catch(() => {}),
      ]).finally(() => setLoading(false));
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
    } catch (err) {
      console.error(err);
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleOpenCase = async () => {
    if (!id || !decisionSupport) return;
    setCreatingCase(true);
    try {
      const signals = decisionSupport.review_priority.why_flagged.map((f: any) => ({
        signal_type: f.signal_type,
        severity: f.severity,
        explanation: f.explanation,
        provenance: f.provenance,
      }));
      const newCase = await createReviewCase({
        project_id: Number(id),
        summary: `Official review: ${project?.category || 'MPLADS Work'} #${project?.work_id || id}`,
        priority: decisionSupport.review_priority.level,
        initial_note: caseNote || 'Case opened from Project Intelligence by authorized official.',
        triggering_signals: signals,
      });
      setShowCaseDialog(false);
      setCaseNote('');
      // Refresh project cases
      getProjectReviewCases(Number(id)).then(setProjectCases).catch(() => {});
      navigate(`/review-cases/${newCase.id}`);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to open review case');
    } finally {
      setCreatingCase(false);
    }
  };

  if (loading) return <div className="p-8 flex items-center gap-2"><Clock className="w-5 h-5 animate-spin" /> Loading official records...</div>;
  if (!project) return <div className="p-8">Project not found.</div>;

  const getPriorityColor = (level: string) => {
    switch (level) {
      case 'CRITICAL': return 'bg-red-100 text-red-800 border-red-200';
      case 'HIGH': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'MEDIUM': return 'bg-amber-100 text-amber-800 border-amber-200';
      default: return 'bg-slate-100 text-slate-800 border-slate-200';
    }
  };

  // Active cases = not RESOLVED or DISMISSED
  const activeCase = projectCases.find((c: any) => ['OPEN','UNDER_REVIEW','ACTION_REQUIRED'].includes(c.status));

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 font-sans">
      {/* Header */}
      <div className="flex justify-between items-start mb-6 border-b pb-6">
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
        <div className="flex space-x-2">
          <button 
            onClick={() => window.print()}
            className="bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 px-4 py-2 rounded-md font-medium shadow-sm transition"
          >
            Export Report
          </button>
        </div>
      </div>

      {decisionSupport && (
        <>
          {/* Review Priority Summary */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-xs overflow-hidden">
            <div className={`p-4 border-b flex items-center gap-3 ${
              decisionSupport.review_priority.level === 'CRITICAL' ? 'bg-red-50 border-red-100' :
              decisionSupport.review_priority.level === 'HIGH' ? 'bg-orange-50 border-orange-100' :
              decisionSupport.review_priority.level === 'MEDIUM' ? 'bg-amber-50 border-amber-100' :
              'bg-slate-50 border-slate-100'
            }`}>
              {decisionSupport.review_priority.level === 'CRITICAL' ? <AlertTriangle className="w-6 h-6 text-red-600" /> : <AlertCircle className="w-6 h-6 text-gray-600" />}
              <div>
                <h2 className="text-lg font-bold text-gray-900">Official Review Priority: <span className={getPriorityColor(decisionSupport.review_priority.level) + " px-2 py-0.5 rounded text-sm ml-2"}>{decisionSupport.review_priority.level}</span></h2>
                <p className="text-sm text-gray-600">Based on {decisionSupport.review_priority.evidence_coverage.toFixed(1)}% evidence coverage.</p>
              </div>
            </div>
            
            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Why Flagged */}
              <div>
                <h3 className="font-bold text-gray-900 mb-3 flex items-center gap-2"><Info className="w-4 h-4 text-indigo-600"/> Why Was This Flagged?</h3>
                {decisionSupport.review_priority.why_flagged.length > 0 ? (
                  <ul className="space-y-3">
                    {decisionSupport.review_priority.why_flagged.map((flag: any, i: number) => (
                      <li key={i} className="bg-gray-50 p-3 rounded-lg border border-gray-100 text-sm">
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-bold text-gray-800">{flag.signal_type}</span>
                          <span className={`text-xs font-bold px-2 py-0.5 rounded ${getPriorityColor(flag.severity)}`}>{flag.severity}</span>
                        </div>
                        <p className="text-gray-600">{flag.explanation}</p>
                        <div className="mt-2 text-xs flex justify-between">
                           <span className="text-gray-400 font-mono">{JSON.stringify(flag.evidence)}</span>
                           <ProvenanceBadge type={flag.provenance} />
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-gray-500 bg-gray-50 p-4 rounded text-center">No critical flags detected.</p>
                )}
              </div>
              
              {/* Evidence Chain */}
              <div>
                <h3 className="font-bold text-gray-900 mb-3 flex items-center gap-2"><Layers className="w-4 h-4 text-indigo-600"/> Evidence Chain</h3>
                <div className="bg-blue-50/50 p-4 rounded-lg border border-blue-100 relative">
                    <div className="absolute left-[27px] top-6 bottom-6 w-0.5 bg-blue-200"></div>
                    <div className="space-y-4 relative z-10">
                       <div className="flex items-start gap-3">
                         <div className="w-6 h-6 rounded-full bg-blue-100 border border-blue-300 flex items-center justify-center shrink-0 mt-0.5 text-blue-600 text-xs font-bold">1</div>
                         <div>
                            <p className="text-sm font-bold text-gray-900">OFFICIAL SEED</p>
                            <p className="text-xs text-gray-600">MoSPI/eSAKSHI Work Stage: {project.work_stage}</p>
                         </div>
                       </div>
                       <div className="flex items-start gap-3">
                         <div className="w-6 h-6 rounded-full bg-indigo-100 border border-indigo-300 flex items-center justify-center shrink-0 mt-0.5 text-indigo-600 text-xs font-bold">2</div>
                         <div>
                            <p className="text-sm font-bold text-gray-900">DERIVED INTELLIGENCE</p>
                            <p className="text-xs text-gray-600">Analytical Proxy + Risk History</p>
                         </div>
                       </div>
                       <div className="flex items-start gap-3">
                         <div className="w-6 h-6 rounded-full bg-purple-100 border border-purple-300 flex items-center justify-center shrink-0 mt-0.5 text-purple-600 text-xs font-bold">3</div>
                         <div>
                            <p className="text-sm font-bold text-gray-900">AI FLAG</p>
                            <p className="text-xs text-gray-600">Projected Completion Risk + Compliance</p>
                         </div>
                       </div>
                       <div className="flex items-start gap-3">
                         <div className="w-6 h-6 rounded-full bg-amber-100 border border-amber-300 flex items-center justify-center shrink-0 mt-0.5 text-amber-600 text-xs font-bold">4</div>
                         <div>
                            <p className="text-sm font-bold text-gray-900">OFFICIAL REVIEW</p>
                            <p className="text-xs text-gray-600">Awaiting human adjudication</p>
                         </div>
                       </div>
                    </div>
                </div>
              </div>
            </div>
          </div>

          {/* Data Limitations Scorecard */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-xs overflow-hidden">
             <div className="p-4 border-b bg-gray-50/50">
               <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2"><Server className="w-5 h-5 text-gray-500"/> Data Limitations & Quality Scorecard</h2>
             </div>
             <div className="p-6 grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                {Object.entries(decisionSupport.data_quality).map(([key, val]) => (
                   <div key={key} className="flex justify-between items-center p-3 bg-gray-50 rounded border border-gray-100">
                     <span className="text-gray-600 capitalize">{key.replace(/_/g, ' ')}</span>
                     <span className={`text-xs font-bold ${val === 'AVAILABLE' ? 'text-emerald-600' : 'text-gray-400'}`}>{val as string}</span>
                   </div>
                ))}
             </div>
          </div>
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Early Warning Center */}
              <div className="bg-white border border-gray-200 rounded-xl shadow-xs overflow-hidden flex flex-col">
                 <div className="p-4 border-b bg-gray-50/50 flex justify-between items-center">
                   <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2"><AlertTriangle className="w-5 h-5 text-amber-600"/> Open Review Center</h2>
                 </div>
                 <div className="p-6 flex-1">
                   {decisionSupport.early_warnings.length > 0 ? (
                      <div className="space-y-3">
                         {decisionSupport.early_warnings.map((w: any) => (
                            <div key={w.id} className="p-3 border rounded-lg bg-red-50/50 border-red-100">
                               <div className="flex justify-between">
                                 <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${getPriorityColor(w.level)}`}>{w.level}</span>
                                 <span className="text-xs text-gray-500 font-mono">{w.status}</span>
                               </div>
                               <p className="mt-2 text-sm text-gray-900 font-medium">{w.explanation}</p>
                               <div className="mt-2 text-[10px]"><ProvenanceBadge type={w.provenance} /></div>
                            </div>
                         ))}
                      </div>
                   ) : (
                     <div className="h-full flex flex-col items-center justify-center text-gray-400 p-8 text-center">
                        <CheckCircle className="w-12 h-12 mb-3 opacity-50" />
                        <p>No open early warnings.</p>
                     </div>
                   )}
                 </div>
              </div>

              {/* Timeline */}
              <div className="bg-white border border-gray-200 rounded-xl shadow-xs overflow-hidden flex flex-col">
                 <div className="p-4 border-b bg-gray-50/50">
                   <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2"><History className="w-5 h-5 text-indigo-600"/> Project Timeline</h2>
                 </div>
                 <div className="p-6 flex-1 max-h-[400px] overflow-y-auto">
                   <div className="space-y-6 relative before:absolute before:inset-0 before:ml-2.5 before:-translate-x-px md:before:ml-[5.5rem] md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-slate-300 before:to-transparent">
                      {decisionSupport.timeline.map((event: any, i: number) => (
                         <div key={i} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
                            <div className="flex items-center justify-center w-6 h-6 rounded-full border border-white bg-indigo-500 shadow-sm shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2" />
                            <div className="w-[calc(100%-2.5rem)] md:w-[calc(50%-1.5rem)] p-4 rounded border border-slate-200 bg-white shadow-xs">
                               <div className="flex items-center justify-between mb-1">
                                 <div className="font-bold text-slate-900 text-sm">{event.event_type}</div>
                                 <time className="font-mono text-xs text-indigo-600 font-semibold">{new Date(event.date).toLocaleDateString()}</time>
                               </div>
                               <div className="text-slate-600 text-xs mb-2">{event.description}</div>
                               <ProvenanceBadge type={event.provenance} />
                            </div>
                         </div>
                      ))}
                   </div>
                 </div>
              </div>
          </div>
        </>
      )}

      {/* ── OFFICIAL REVIEW CASE SECTION ── */}
      <div className="bg-white border border-indigo-200 rounded-xl shadow-xs overflow-hidden">
        <div className="p-4 border-b bg-indigo-50/50 flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <FolderOpen className="w-5 h-5 text-indigo-600" /> Official Review Case
          </h2>
          {!activeCase ? (
            <button
              onClick={() => setShowCaseDialog(true)}
              disabled={!decisionSupport}
              className="bg-indigo-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-indigo-700 shadow-sm transition disabled:opacity-50"
            >
              Open Review Case
            </button>
          ) : (
            <Link
              to={`/review-cases/${activeCase.id}`}
              className="flex items-center gap-1 text-indigo-600 hover:underline text-sm font-medium"
            >
              View Case <ExternalLink className="w-3.5 h-3.5" />
            </Link>
          )}
        </div>
        <div className="p-5">
          {activeCase ? (
            <div className="space-y-2">
              <div className="flex justify-between text-sm"><span className="text-gray-500">Reference</span><span className="font-mono font-bold text-indigo-700">{activeCase.case_reference}</span></div>
              <div className="flex justify-between text-sm"><span className="text-gray-500">Status</span><span className="font-bold text-gray-800">{activeCase.status?.replace('_',' ')}</span></div>
              <div className="flex justify-between text-sm"><span className="text-gray-500">Priority</span><span className="font-bold text-gray-800">{activeCase.priority}</span></div>
              <div className="flex justify-between text-sm"><span className="text-gray-500">Assigned</span><span className="font-bold text-gray-800">{activeCase.assigned_to?.username || 'Unassigned'}</span></div>
              <div className="flex justify-between text-sm"><span className="text-gray-500">Opened</span><span className="font-bold text-gray-800">{new Date(activeCase.opened_at).toLocaleDateString()}</span></div>
            </div>
          ) : (
            <div className="text-center py-4 text-gray-400">
              <FolderOpen className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">No active review case. Open one to begin the investigation workflow.</p>
              <p className="text-xs mt-1">AI signals are recommendations only. Officials decide and act.</p>
            </div>
          )}
        </div>
      </div>

      {/* Open Case Dialog */}
      {showCaseDialog && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-2">Open Official Review Case</h3>
            <p className="text-sm text-gray-600 mb-4">
              Creates an official review case for Project #{id}.
              AI signals are pre-populated. <strong>Officials decide and act.</strong>
            </p>
            {decisionSupport?.review_priority && (
              <div className="mb-4 p-3 bg-orange-50 border border-orange-100 rounded-lg text-sm">
                <p className="font-bold text-orange-800">Priority: {decisionSupport.review_priority.level}</p>
                <p className="text-orange-700 text-xs mt-1">{decisionSupport.review_priority.contributing_signals?.slice(0,3).join(' · ')}</p>
              </div>
            )}
            <textarea
              value={caseNote}
              onChange={e => setCaseNote(e.target.value)}
              rows={3}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm mb-4 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
              placeholder="Initial note (optional)..."
            />
            <div className="flex gap-3">
              <button onClick={() => { setShowCaseDialog(false); setCaseNote(''); }} className="flex-1 border border-gray-200 text-gray-600 py-2 rounded-lg text-sm font-medium hover:bg-gray-50">Cancel</button>
              <button onClick={handleOpenCase} disabled={creatingCase} className="flex-1 bg-indigo-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 shadow-sm">
                {creatingCase ? 'Opening...' : 'Open Case'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Official Actions */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-xs p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
          <MessageSquare className="mr-2 h-5 w-5 text-indigo-600" />
          Official Review Adjudication
        </h2>
        <form onSubmit={handleReviewSubmit} className="space-y-4 max-w-2xl">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Review Action</label>
            <select
              value={reviewForm.action}
              onChange={(e) => setReviewForm({ ...reviewForm, action: e.target.value })}
              className="w-full border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 p-2 border"
            >
              <option value="COMMENT">Add Comment / Note</option>
              <option value="FLAG">Flag for Investigation</option>
              <option value="CLEAR">Clear All Warnings</option>
              <option value="HALT">Recommend Project Halt</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Official Remarks</label>
            <textarea
              required
              rows={3}
              value={reviewForm.comment}
              onChange={(e) => setReviewForm({ ...reviewForm, comment: e.target.value })}
              className="w-full border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 p-2 border"
              placeholder="Enter official remarks..."
            />
          </div>
          <button
            type="submit"
            disabled={submittingReview}
            className="bg-indigo-600 text-white px-4 py-2 rounded shadow-sm hover:bg-indigo-700 disabled:opacity-50 text-sm font-medium"
          >
            {submittingReview ? 'Submitting...' : 'Submit Official Record'}
          </button>
        </form>

        {reviews.length > 0 && (
          <div className="mt-8 pt-6 border-t border-gray-100">
            <h3 className="font-bold text-gray-900 text-sm mb-4">Past Adjudications</h3>
            <div className="space-y-4">
              {reviews.map((r: any) => (
                <div key={r.id} className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-bold text-gray-900 text-sm">{r.reviewed_by}</span>
                    <span className={`text-xs font-bold px-2 py-1 rounded ${
                      r.action === 'CLEAR' ? 'bg-emerald-100 text-emerald-800' :
                      r.action === 'FLAG' || r.action === 'HALT' ? 'bg-red-100 text-red-800' :
                      'bg-gray-200 text-gray-800'
                    }`}>
                      {r.action}
                    </span>
                  </div>
                  <p className="text-gray-700 text-sm">{r.comment}</p>
                  <div className="text-xs text-gray-400 mt-2 font-mono">
                    {new Date(r.created_at).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

    </div>
  );
};
