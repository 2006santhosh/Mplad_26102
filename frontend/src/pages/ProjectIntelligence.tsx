import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getProjectDetails, getDecisionSupport, getReviews, postReview } from '../lib/api';
import { 
  ShieldCheck, AlertTriangle, AlertCircle, Clock, CheckCircle, 
  History, Info, MessageSquare, Server, Layers 
} from 'lucide-react';
import { ProvenanceBadge } from '../components/ProvenanceBadge';

export const ProjectIntelligence = () => {
  const { id } = useParams();
  const [project, setProject] = useState<any>(null);
  const [decisionSupport, setDecisionSupport] = useState<any>(null);
  const [reviews, setReviews] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [reviewForm, setReviewForm] = useState({ reviewed_by: 'Authorized Official', action: 'COMMENT', comment: '' });
  const [submittingReview, setSubmittingReview] = useState(false);

  useEffect(() => {
    if (id) {
      const numId = Number(id);
      setLoading(true);
      Promise.all([
        getProjectDetails(numId).then(setProject),
        getDecisionSupport(numId).then(setDecisionSupport),
        getReviews(numId).then(setReviews).catch(() => {})
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
