import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface TrendDataPoint {
  date: string;
  value: number;
  is_invalid?: boolean;
  note?: string;
}

interface TrendChartProps {
  data: TrendDataPoint[];
  title: string;
  color: string;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-white border border-gray-200 p-3 shadow-lg rounded">
        <p className="text-sm font-semibold text-gray-700 mb-1">{label}</p>
        <p className="text-sm text-gray-900">
          Value: <span className="font-bold">{data.value}</span>
        </p>
        {data.is_invalid && (
          <p className="text-xs text-red-600 font-semibold mt-1">
            ⚠ {data.note || 'Invalid Value'}
          </p>
        )}
      </div>
    );
  }
  return null;
};

export function TrendChart({ data, title, color }: TrendChartProps) {
  if (!data || data.length === 0) {
    return <div className="p-4 text-sm text-gray-500 italic">No trend data available for {title}</div>;
  }

  return (
    <div className="w-full h-64 mt-4">
      <h4 className="text-sm font-semibold text-gray-700 mb-2">{title}</h4>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <Line 
            type="monotone" 
            dataKey="value" 
            stroke={color} 
            strokeWidth={2} 
            dot={(props: any) => {
              const { cx, cy, payload } = props;
              if (payload.is_invalid) {
                return <circle cx={cx} cy={cy} r={5} stroke="red" strokeWidth={2} fill="white" />;
              }
              return <circle cx={cx} cy={cy} r={4} stroke={color} strokeWidth={1} fill={color} />;
            }}
            activeDot={{ r: 6 }} 
          />
          <CartesianGrid stroke="#ccc" strokeDasharray="5 5" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} width={80} />
          <Tooltip content={<CustomTooltip />} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
