import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { useState, useMemo } from 'react';

// Fix for default marker icons in React Leaflet
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

export const ProjectMap = ({ projects }: { projects: any[] }) => {
  // Center roughly on India
  const center: [number, number] = [20.5937, 78.9629];
  
  const [filter, setFilter] = useState('ALL');

  const { validProjects, totalProjects, validCount, unavailableCount, coverage } = useMemo(() => {
    let valid = 0;
    let unavailable = 0;
    const validProjs: any[] = [];
    
    projects.forEach(p => {
      // Very basic coordinate validation equivalent to geo_utils.validate_coordinates
      const lat = parseFloat(p.latitude);
      const lng = parseFloat(p.longitude);
      
      const isValid = 
        p.latitude !== null && p.longitude !== null &&
        !isNaN(lat) && !isNaN(lng) && 
        (lat !== 0 || lng !== 0) &&
        lat >= -90 && lat <= 90 &&
        lng >= -180 && lng <= 180;
        
      if (isValid) {
        valid++;
        // Apply filter
        if (filter === 'ALL' || 
            (filter === 'HIGH_RISK' && ['HIGH', 'CRITICAL'].includes(p.latest_risk_level)) ||
            (filter === 'OFFICIAL_GPS' && p.gps_provenance === 'OFFICIAL')) {
          validProjs.push(p);
        }
      } else {
        unavailable++;
      }
    });
    
    const total = projects.length;
    const cov = total > 0 ? (valid / total) * 100 : 0;
    
    return { validProjects: validProjs, totalProjects: total, validCount: valid, unavailableCount: unavailable, coverage: cov };
  }, [projects, filter]);

  return (
    <div className="relative">
      <div className="absolute top-4 left-4 z-[1000] bg-white p-3 rounded shadow-md text-sm border border-gray-200">
        <h4 className="font-bold text-gray-900 mb-1">Spatial Data Coverage</h4>
        <div className="text-gray-700">
          <p>Coverage: <span className="font-mono font-semibold">{coverage.toFixed(1)}%</span></p>
          <p>Available: <span className="font-mono font-semibold text-green-700">{validCount} / {totalProjects}</span></p>
          <p>Unavailable: <span className="font-mono font-semibold text-red-700">{unavailableCount} / {totalProjects}</span></p>
        </div>
        
        {coverage === 0 && (
          <div className="mt-2 text-xs text-red-600 bg-red-50 p-2 rounded border border-red-100 max-w-xs">
            GPS data is unavailable in the current official dataset. Spatial project-level analysis is therefore NOT_ASSESSABLE. No fake coordinates are generated.
          </div>
        )}
        
        <div className="mt-3 pt-2 border-t border-gray-100">
          <select 
            value={filter} 
            onChange={(e) => setFilter(e.target.value)}
            className="w-full text-xs border-gray-300 rounded p-1"
          >
            <option value="ALL">All Mappable Projects</option>
            <option value="HIGH_RISK">High/Critical Risk Only</option>
            <option value="OFFICIAL_GPS">Official GPS Only</option>
          </select>
        </div>
      </div>

      <div className="h-96 w-full rounded-lg overflow-hidden border border-gray-200 shadow-sm z-0 relative">
        <MapContainer center={center} zoom={4} className="h-full w-full">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {validProjects.map((p) => {
            return (
              <Marker key={p.id} position={[parseFloat(p.latitude), parseFloat(p.longitude)]}>
                <Popup>
                  <div className="text-sm">
                    <strong>{p.location || 'Unknown Location'}</strong><br/>
                    {p.category || 'Unknown Category'}<br/>
                    {p.sanctioned_amount ? `₹${p.sanctioned_amount.toLocaleString()}` : 'Amount Unknown'}<br/>
                    <div className="mt-2 text-xs inline-block bg-gray-100 text-gray-800 px-2 py-0.5 rounded font-mono border border-gray-200">
                      📍 {p.gps_provenance} GPS
                    </div>
                  </div>
                </Popup>
              </Marker>
            );
          })}
        </MapContainer>
      </div>
    </div>
  );
};
