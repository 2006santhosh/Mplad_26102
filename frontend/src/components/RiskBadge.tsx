

export const RiskBadge = ({ level }: { level: string | null }) => {
  if (!level) return <span className="px-2 py-1 bg-gray-100 text-gray-800 rounded text-xs font-bold">UNASSESSED</span>;
  
  const colors: Record<string, string> = {
    LOW: 'bg-green-100 text-green-800',
    MEDIUM: 'bg-yellow-100 text-yellow-800',
    HIGH: 'bg-red-100 text-red-800',
    CRITICAL: 'bg-red-600 text-white'
  };

  return (
    <span className={`px-2 py-1 rounded text-xs font-bold ${colors[level] || 'bg-gray-100'}`}>
      {level}
    </span>
  );
};
