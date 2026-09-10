import React from 'react';
import { ShieldCheck, BrainCircuit, SearchX, Activity, AlertCircle } from 'lucide-react';

interface ProvenanceBadgeProps {
  type: 'OFFICIAL' | 'DERIVED' | 'AI ASSESSMENT' | 'UNAVAILABLE' | 'NOT_AVAILABLE' | 'NOT_ASSESSABLE' | 'OFFICIAL ACTION' | 'SYNTHETIC' | string;
  className?: string;
  prefix?: string;
  title?: string;
}

export const ProvenanceBadge: React.FC<ProvenanceBadgeProps> = ({ type, className = '', prefix, title }) => {
  if (!type) return null;

  const t = type.toUpperCase();
  const normalized = t === 'NOT_AVAILABLE' ? 'NOT_AVAILABLE' : t;

  let colors = 'bg-gray-100 text-gray-700 border-gray-200';
  let Icon = null;
  let tooltip = title || 'Provenance status';

  if (normalized === 'OFFICIAL') {
    colors = 'bg-emerald-100 text-emerald-800 border-emerald-300';
    Icon = ShieldCheck;
    tooltip = 'Official source value from the government dataset.';
  } else if (normalized === 'DERIVED') {
    colors = 'bg-blue-100 text-blue-800 border-blue-300';
    Icon = Activity;
    tooltip = 'Derived from official fields or analytical logic.';
  } else if (normalized === 'AI ASSESSMENT') {
    colors = 'bg-indigo-100 text-indigo-800 border-indigo-300';
    Icon = BrainCircuit;
    tooltip = 'AI-generated analytical assessment; not an official government determination.';
  } else if (normalized === 'UNAVAILABLE' || normalized === 'NOT_AVAILABLE') {
    colors = 'bg-gray-100 text-gray-500 border-gray-300';
    Icon = SearchX;
    tooltip = 'Required source field is absent in the official dataset. No value is inferred.';
  } else if (normalized === 'NOT_ASSESSABLE') {
    colors = 'bg-slate-100 text-slate-600 border-slate-300';
    Icon = AlertCircle;
    tooltip = 'The required evidence is not assessable from the available official data.';
  } else if (normalized === 'OFFICIAL ACTION') {
    colors = 'bg-amber-100 text-amber-800 border-amber-300';
    Icon = ShieldCheck;
    tooltip = 'Official action taken by an authorized human reviewer.';
  } else if (normalized === 'SYNTHETIC') {
    colors = 'bg-red-100 text-red-800 border-red-300';
    Icon = AlertCircle;
    tooltip = 'Synthetic or demo-only value; not part of the official government dataset.';
  }

  return (
    <span
      className={`inline-flex items-center gap-1 text-[10px] font-bold px-1.5 py-0.5 rounded border shadow-xs ${colors} ${className}`}
      title={tooltip}
    >
      {Icon && <Icon className="w-3 h-3" />}
      {prefix && <span className="opacity-75 font-medium">{prefix}</span>}
      {normalized}
    </span>
  );
};
