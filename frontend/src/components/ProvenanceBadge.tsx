import React from 'react';
import { ShieldCheck, BrainCircuit, SearchX, Activity, AlertCircle } from 'lucide-react';

interface ProvenanceBadgeProps {
  type: 'OFFICIAL' | 'DERIVED' | 'AI ASSESSMENT' | 'UNAVAILABLE' | 'SYNTHETIC' | string;
  className?: string;
}

export const ProvenanceBadge: React.FC<ProvenanceBadgeProps> = ({ type, className = '' }) => {
  if (!type) return null;

  const t = type.toUpperCase();

  let colors = 'bg-gray-100 text-gray-700 border-gray-200';
  let Icon = null;

  if (t === 'OFFICIAL') {
    colors = 'bg-emerald-100 text-emerald-800 border-emerald-300';
    Icon = ShieldCheck;
  } else if (t === 'DERIVED') {
    colors = 'bg-blue-100 text-blue-800 border-blue-300';
    Icon = Activity;
  } else if (t === 'AI ASSESSMENT') {
    colors = 'bg-indigo-100 text-indigo-800 border-indigo-300';
    Icon = BrainCircuit;
  } else if (t === 'UNAVAILABLE') {
    colors = 'bg-gray-100 text-gray-500 border-gray-300';
    Icon = SearchX;
  } else if (t === 'SYNTHETIC') {
    colors = 'bg-red-100 text-red-800 border-red-300';
    Icon = AlertCircle;
  }

  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-bold px-1.5 py-0.5 rounded border shadow-xs ${colors} ${className}`}>
      {Icon && <Icon className="w-3 h-3" />}
      {t}
    </span>
  );
};
