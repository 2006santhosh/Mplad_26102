import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getReviewCase, updateReviewCase, addCaseNote, addCaseAction,
} from '../lib/api';
import {
  ShieldAlert, AlertTriangle, CheckCircle, Clock, XCircle,
  FileText, MessageSquare, Zap, User, History,
  ChevronRight, Info, Lock, AlertCircle
} from 'lucide-react';
import { ProvenanceBadge } from '../components/ProvenanceBadge';

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

const AUDIT_ACTION_LABELS: Record<string, string> = {
  CASE_CREATED: 'Case opened',
  CASE_ASSIGNED: 'Case assigned',
  STATUS_CHANGED: 'Status changed',
  NOTE_ADDED: 'Official note added',
  EVIDENCE_ATTACHED: 'Evidence attached',
  COMMENT_RECORDED: 'Official comment recorded',
  FLAG_RECORDED: 'Flagged for investigation',
  CLEAR_RECORDED: 'Cleared — no further action required',
  HALT_RECORDED: 'Official halt action recorded',
  CASE_RESOLVED: 'Case resolved',
  CASE_DISMISSED: 'Case dismissed',
};

const AUDIT_ACTION_COLORS: Record<string, string> = {
  CASE_CREATED: 'bg-blue-100 border-blue-300 text-blue-800',
  CASE_ASSIGNED: 'bg-purple-100 border-purple-300 text-purple-800',
  STATUS_CHANGED: 'bg-amber-100 border-amber-300 text-amber-800',
  NOTE_ADDED: 'bg-indigo-100 border-indigo-300 text-indigo-800',
  COMMENT_RECORDED: 'bg-gray-100 border-gray-300 text-gray-700',
  FLAG_RECORDED: 'bg-orange-100 border-orange-300 text-orange-800',
  CLEAR_RECORDED: 'bg-emerald-100 border-emerald-300 text-emerald-800',
  HALT_RECORDED: 'bg-red-100 border-red-300 text-red-900',
  CASE_RESOLVED: 'bg-emerald-100 border-emerald-300 text-emerald-900',
  CASE_DISMISSED: 'bg-gray-100 border-gray-300 text-gray-700',
};

// Status transitions allowed from each state
const NEXT_STATUSES: Record<string, string[]> = {
  OPEN: ['UNDER_REVIEW', 'DISMISSED'],
  UNDER_REVIEW: ['ACTION_REQUIRED', 'RESOLVED', 'DISMISSED'],
  ACTION_REQUIRED: ['RESOLVED', 'UNDER_REVIEW'],
  RESOLVED: [],
  DISMISSED: [],
};

export const ReviewCaseDetail = () => {
  const { id } = useParams();
  const [caseData, setCaseData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const role = localStorage.getItem('role') || 'Auditor';

  // Note form
  const [noteContent, setNoteContent] = useState('');
  const [submittingNote, setSubmittingNote] = useState(false);

  // Action form
  const [actionForm, setActionForm] = useState({ action: 'COMMENT', comment: '', confirmed: false });
  const [submittingAction, setSubmittingAction] = useState(false);
  const [showHaltConfirm, setShowHaltConfirm] = useState(false);

  // Status update
  const [statusForm, setStatusForm] = useState({ status: '', resolution_note: '' });
  const [submittingStatus, setSubmittingStatus] = useState(false);

  // Assignment
  const [assignUserId, setAssignUserId] = useState('');
  const [submittingAssign, setSubmittingAssign] = useState(false);

  const loadCase = async () => {
    if (!id) return;
    try {
      const data = await getReviewCase(Number(id));
      setCaseData(data);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to load case');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCase();
  }, [id]);

  const isTerminal = caseData?.status === 'RESOLVED' || caseData?.status === 'DISMISSED';
  const canWrite = ['Admin', 'State', 'District', 'Auditor'].includes(role);
  const canHalt = ['Admin', 'State'].includes(role);

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!noteContent.trim() || !id) return;
    setSubmittingNote(true);
    try {
      await addCaseNote(Number(id), { content: noteContent });
      setNoteContent('');
      await loadCase();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to add note');
    } finally {
      setSubmittingNote(false);
    }
  };

  const handleAddAction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!actionForm.comment.trim() || !id) return;
    if (actionForm.action === 'HALT' && !actionForm.confirmed) {
      setShowHaltConfirm(true);
      return;
    }
    setSubmittingAction(true);
    try {
      await addCaseAction(Number(id), actionForm);
      setActionForm({ action: 'COMMENT', comment: '', confirmed: false });
      setShowHaltConfirm(false);
      await loadCase();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to record action');
    } finally {
      setSubmittingAction(false);
    }
  };

  const handleStatusUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!statusForm.status || !id) return;
    const needsReason = ['RESOLVED', 'DISMISSED'].includes(statusForm.status);
    if (needsReason && !statusForm.resolution_note.trim()) {
      alert('A resolution reason is required to resolve or dismiss a case.');
      return;
    }
    setSubmittingStatus(true);
    try {
      await updateReviewCase(Number(id), statusForm);
      setStatusForm({ status: '', resolution_note: '' });
      await loadCase();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update status');
    } finally {
      setSubmittingStatus(false);
    }
  };

  const handleAssign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignUserId || !id) return;
    setSubmittingAssign(true);
    try {
      await updateReviewCase(Number(id), { assigned_to_id: parseInt(assignUserId) });
      setAssignUserId('');
      await loadCase();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to assign case');
    } finally {
      setSubmittingAssign(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center gap-3 text-gray-500">
        <Clock className="w-5 h-5 animate-spin" /> Loading review case...
      </div>
    );
  }

  if (error || !caseData) {
    return (
      <div className="p-8">
        <p className="text-red-600">{error || 'Case not found.'}</p>
        <Link to="/review-cases" className="text-indigo-600 hover:underline text-sm mt-2 inline-block">← Back to Review Cases</Link>
      </div>
    );
  }

  const nextStatuses = NEXT_STATUSES[caseData.status] || [];

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8 font-sans">
      {/* Navigation */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Link to="/review-cases" className="hover:text-indigo-600 font-medium">Review Cases</Link>
        <ChevronRight className="w-4 h-4" />
        <span className="font-mono text-indigo-700">{caseData.case_reference}</span>
      </div>

      {/* ── Case Header ── */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="p-6 border-b bg-gradient-to-r from-slate-50 to-indigo-50/30">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <div className="flex items-center gap-3 flex-wrap">
                <ShieldAlert className="w-6 h-6 text-indigo-600" />
                <h1 className="text-2xl font-bold text-gray-900 font-mono">{caseData.case_reference}</h1>
                <span className={`text-xs font-bold px-3 py-1 rounded-full border ${STATUS_COLORS[caseData.status]}`}>
                  {caseData.status?.replace('_', ' ')}
                </span>
                <span className={`text-xs font-bold px-3 py-1 rounded-full border ${PRIORITY_COLORS[caseData.priority]}`}>
                  {caseData.priority} PRIORITY
                </span>
              </div>
              <p className="text-gray-600 mt-2 text-sm max-w-2xl">{caseData.summary || 'No summary recorded.'}</p>
            </div>
            <Link
              to={`/projects/${caseData.project_id}`}
              className="text-sm text-indigo-600 hover:underline font-medium flex items-center gap-1"
            >
              View Project #{caseData.project_id} <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide font-semibold">Project</p>
              <p className="text-sm font-semibold text-gray-800">#{caseData.project_id}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide font-semibold">Opened by</p>
              <p className="text-sm font-semibold text-gray-800">{caseData.opened_by?.username || '—'}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide font-semibold">Assigned to</p>
              <p className="text-sm font-semibold text-gray-800">{caseData.assigned_to?.username || 'Unassigned'}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide font-semibold">Opened</p>
              <p className="text-sm font-semibold text-gray-800">{new Date(caseData.opened_at).toLocaleDateString()}</p>
            </div>
            {caseData.resolved_at && (
              <div>
                <p className="text-xs text-gray-400 uppercase tracking-wide font-semibold">Resolved</p>
                <p className="text-sm font-semibold text-gray-800">{new Date(caseData.resolved_at).toLocaleString()}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Triggering Signals ── */}
      {caseData.triggering_signals?.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b bg-orange-50/30 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-orange-600" />
            <h2 className="font-bold text-gray-900">Triggering Signals</h2>
            <span className="text-xs text-gray-400 font-normal ml-1">— what prompted this review case</span>
          </div>
          <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-3">
            {caseData.triggering_signals.map((signal: any, i: number) => (
              <div key={i} className="flex items-start gap-3 bg-orange-50/50 p-3 rounded-lg border border-orange-100">
                <Zap className="w-4 h-4 text-orange-500 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-gray-900">{signal.signal_type || signal.type}</p>
                  {signal.explanation && <p className="text-xs text-gray-600 mt-0.5">{signal.explanation}</p>}
                  <div className="mt-1 flex gap-2">
                    {signal.severity && (
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${PRIORITY_COLORS[signal.severity] || 'bg-gray-100 text-gray-600'}`}>
                        {signal.severity}
                      </span>
                    )}
                    <ProvenanceBadge type={signal.provenance || 'AI ASSESSMENT'} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Initial Note ── */}
      {caseData.initial_note && (
        <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4 flex gap-3">
          <Info className="w-5 h-5 text-indigo-500 shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-semibold text-indigo-600 uppercase tracking-wide mb-1">Initial Note at Case Opening</p>
            <p className="text-sm text-gray-800">{caseData.initial_note}</p>
          </div>
        </div>
      )}

      {/* ── Official Notes ── */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b bg-gray-50/50 flex items-center gap-2">
          <FileText className="w-5 h-5 text-gray-500" />
          <h2 className="font-bold text-gray-900">Official Notes</h2>
          <span className="text-xs text-gray-400">— immutable, append-only</span>
          <ProvenanceBadge type="OFFICIAL ACTION" />
        </div>
        <div className="p-6 space-y-4">
          {caseData.notes?.length > 0 ? caseData.notes.map((note: any) => (
            <div key={note.id} className="bg-gray-50 rounded-lg p-4 border border-gray-100">
              <div className="flex justify-between items-center mb-2">
                <div className="flex items-center gap-2">
                  <User className="w-4 h-4 text-gray-400" />
                  <span className="text-sm font-semibold text-gray-800">{note.author?.username || 'Unknown'}</span>
                  <span className="text-xs text-gray-400">({note.author?.role})</span>
                </div>
                <time className="text-xs text-gray-400 font-mono">{new Date(note.created_at).toLocaleString()}</time>
              </div>
              <p className="text-sm text-gray-700">{note.content}</p>
              <div className="mt-2"><ProvenanceBadge type={note.provenance} /></div>
            </div>
          )) : (
            <p className="text-sm text-gray-400 text-center py-4">No official notes recorded yet.</p>
          )}

          {/* Add Note Form */}
          {canWrite && !isTerminal && (
            <form onSubmit={handleAddNote} className="mt-4 border-t pt-4 space-y-3">
              <label className="block text-sm font-medium text-gray-700">Add Official Note</label>
              <textarea
                value={noteContent}
                onChange={e => setNoteContent(e.target.value)}
                rows={3}
                required
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
                placeholder="e.g. Documents requested from district authority. Site verification scheduled."
              />
              <button
                type="submit"
                disabled={submittingNote || !noteContent.trim()}
                className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 shadow-sm transition"
              >
                {submittingNote ? 'Adding...' : 'Add Official Note'}
              </button>
            </form>
          )}
        </div>
      </div>

      {/* ── Official Actions ── */}
      {canWrite && !isTerminal && (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b bg-gray-50/50 flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-indigo-600" />
            <h2 className="font-bold text-gray-900">Record Official Action</h2>
          </div>
          <div className="p-6">
            <form onSubmit={handleAddAction} className="space-y-4 max-w-2xl">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Action Type</label>
                <select
                  value={actionForm.action}
                  onChange={e => { setActionForm({ ...actionForm, action: e.target.value, confirmed: false }); setShowHaltConfirm(false); }}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 bg-gray-50 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
                >
                  <option value="COMMENT">COMMENT — Record an official observation</option>
                  <option value="FLAG">FLAG — Mark for further investigation</option>
                  <option value="CLEAR">CLEAR — Signal does not require continued review</option>
                  {canHalt && <option value="HALT">HALT — Order an official halt/action</option>}
                </select>
              </div>

              {actionForm.action === 'HALT' && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle className="w-5 h-5 text-red-600" />
                    <span className="font-bold text-red-800 text-sm">HALT — Official Authorization Required</span>
                  </div>
                  {showHaltConfirm && (
                    <p className="text-xs text-red-700 mb-2 font-medium">
                      Please confirm that the reviewer is authorized to order this official halt action.
                    </p>
                  )}
                  <p className="text-xs text-red-700 mb-3">
                    HALT is an official action by an authorized senior officer. AI did not trigger this.
                    Only an authorized official may record this action. This will be permanently audited.
                  </p>
                  <label className="flex items-center gap-2 text-sm text-red-800 font-medium cursor-pointer">
                    <input
                      type="checkbox"
                      checked={actionForm.confirmed}
                      onChange={e => setActionForm({ ...actionForm, confirmed: e.target.checked })}
                      className="rounded border-red-300"
                    />
                    I confirm that I am an authorized official and I am ordering this halt action
                  </label>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Reason / Remarks</label>
                <textarea
                  value={actionForm.comment}
                  onChange={e => setActionForm({ ...actionForm, comment: e.target.value })}
                  rows={3}
                  required
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
                  placeholder="Provide a clear official reason for this action..."
                />
              </div>
              <button
                type="submit"
                disabled={submittingAction || !actionForm.comment.trim() || (actionForm.action === 'HALT' && !actionForm.confirmed)}
                className={`px-4 py-2 rounded-lg text-sm font-medium shadow-sm transition disabled:opacity-50 ${
                  actionForm.action === 'HALT'
                    ? 'bg-red-600 text-white hover:bg-red-700'
                    : 'bg-indigo-600 text-white hover:bg-indigo-700'
                }`}
              >
                {submittingAction ? 'Submitting...' : `Record ${actionForm.action} Action`}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* ── Status Workflow ── */}
      {canWrite && !isTerminal && nextStatuses.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b bg-gray-50/50">
            <h2 className="font-bold text-gray-900">Update Case Status</h2>
            <p className="text-xs text-gray-400 mt-1">Allowed from <strong>{caseData.status}</strong>: {nextStatuses.join(', ')}</p>
          </div>
          <div className="p-6">
            <form onSubmit={handleStatusUpdate} className="space-y-4 max-w-xl">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">New Status</label>
                <select
                  value={statusForm.status}
                  onChange={e => setStatusForm({ ...statusForm, status: e.target.value })}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 bg-gray-50 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
                  required
                >
                  <option value="">Select new status...</option>
                  {nextStatuses.map(s => (
                    <option key={s} value={s}>{s.replace('_', ' ')}</option>
                  ))}
                </select>
              </div>
              {['RESOLVED', 'DISMISSED'].includes(statusForm.status) && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Resolution Reason <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    value={statusForm.resolution_note}
                    onChange={e => setStatusForm({ ...statusForm, resolution_note: e.target.value })}
                    rows={3}
                    required
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
                    placeholder={statusForm.status === 'DISMISSED'
                      ? 'e.g. Verified against supporting documents. Signal was not substantiated.'
                      : 'e.g. Reviewed all evidence. Confirmed expenditure within sanctioned limits.'}
                  />
                </div>
              )}
              <button
                type="submit"
                disabled={submittingStatus || !statusForm.status}
                className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 shadow-sm transition"
              >
                {submittingStatus ? 'Updating...' : 'Update Status'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* ── Assignment ── */}
      {canWrite && !isTerminal && (
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b bg-gray-50/50">
            <h2 className="font-bold text-gray-900">Assign Case Officer</h2>
          </div>
          <div className="p-6">
            <form onSubmit={handleAssign} className="flex gap-3 items-end max-w-md">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">User ID</label>
                <input
                  type="number"
                  value={assignUserId}
                  onChange={e => setAssignUserId(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
                  placeholder="User ID (1=admin, 2=state, 3=district, 4=auditor)"
                />
              </div>
              <button
                type="submit"
                disabled={submittingAssign || !assignUserId}
                className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 shadow-sm"
              >
                {submittingAssign ? 'Assigning...' : 'Assign'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* ── Resolution Note ── */}
      {caseData.resolution_note && (
        <div className={`rounded-xl border p-5 ${caseData.status === 'RESOLVED' ? 'bg-emerald-50 border-emerald-200' : 'bg-gray-50 border-gray-200'}`}>
          <div className="flex items-center gap-2 mb-2">
            {caseData.status === 'RESOLVED'
              ? <CheckCircle className="w-5 h-5 text-emerald-600" />
              : <XCircle className="w-5 h-5 text-gray-500" />}
            <span className="font-bold text-gray-900 text-sm">
              {caseData.status === 'RESOLVED' ? 'Resolution' : 'Dismissal'} Note
            </span>
          </div>
          <p className="text-sm text-gray-700">{caseData.resolution_note}</p>
          {caseData.resolved_at && (
            <p className="text-xs text-gray-400 mt-2 font-mono">{new Date(caseData.resolved_at).toLocaleString()}</p>
          )}
        </div>
      )}

      {/* ── Audit Trail ── */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b bg-gray-50/50 flex items-center gap-2">
          <History className="w-5 h-5 text-indigo-600" />
          <h2 className="font-bold text-gray-900">Audit Trail</h2>
          <span className="text-xs text-gray-400">— append-only, immutable record</span>
          <Lock className="w-3.5 h-3.5 text-gray-400" />
        </div>
        <div className="p-6">
          {caseData.audit_events?.length > 0 ? (
            <div className="relative">
              <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gradient-to-b from-indigo-200 via-indigo-100 to-transparent" />
              <div className="space-y-6">
                {[...caseData.audit_events].reverse().map((event: any) => (
                  <div key={event.id} className="flex gap-4 relative">
                    <div className="w-8 h-8 rounded-full bg-white border-2 border-indigo-300 flex items-center justify-center shrink-0 z-10">
                      <AlertCircle className="w-3.5 h-3.5 text-indigo-500" />
                    </div>
                    <div className={`flex-1 rounded-lg border p-4 ${AUDIT_ACTION_COLORS[event.action] || 'bg-gray-50 border-gray-200'}`}>
                      <div className="flex justify-between items-start flex-wrap gap-2">
                        <div>
                          <p className="text-sm font-bold">{AUDIT_ACTION_LABELS[event.action] || event.action}</p>
                          {event.previous_status && event.new_status && (
                            <p className="text-xs mt-0.5 opacity-75">
                              {event.previous_status} → {event.new_status}
                            </p>
                          )}
                        </div>
                        <div className="text-right">
                          <p className="text-xs font-mono opacity-75">{new Date(event.created_at).toLocaleString()}</p>
                          <p className="text-xs font-semibold mt-0.5">
                            {event.user?.username} <span className="opacity-60">({event.user?.role})</span>
                          </p>
                        </div>
                      </div>
                      {event.comment && (
                        <p className="text-xs mt-2 opacity-80 italic">"{event.comment}"</p>
                      )}
                      <div className="mt-2"><ProvenanceBadge type={event.provenance} /></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-400 text-center py-6">No audit events recorded.</p>
          )}
        </div>
      </div>

      {/* ── Provenance Notice ── */}
      <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-sm text-blue-700">
        <strong>Provenance notice:</strong> Case actions recorded here are{' '}
        <code className="bg-blue-100 px-1 rounded font-mono text-xs">OFFICIAL ACTION</code>.
        The underlying AI signals (early warnings, risk assessments) remain as{' '}
        <code className="bg-blue-100 px-1 rounded font-mono text-xs">AI ASSESSMENT</code> records
        and are never deleted. <strong>AI recommends. Officials decide.</strong>
      </div>
    </div>
  );
};
