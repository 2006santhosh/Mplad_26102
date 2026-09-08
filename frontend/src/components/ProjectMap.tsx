import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

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
  
  return (
    <div className="h-96 w-full rounded-lg overflow-hidden border border-gray-200 shadow-sm z-0 relative">
      <MapContainer center={center} zoom={4} className="h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {/* Render markers only for projects with valid coordinates */}
        {projects.map((p) => {
          const lat = parseFloat(p.latitude);
          const lng = parseFloat(p.longitude);
          
          if (isNaN(lat) || isNaN(lng) || (lat === 0 && lng === 0)) {
            return null; // Skip rendering if coordinates are missing or invalid
          }
          
          return (
            <Marker key={p.id} position={[lat, lng]}>
              <Popup>
                <div className="text-sm">
                  <strong>{p.location || 'Unknown Location'}</strong><br/>
                  {p.category || 'Unknown Category'}<br/>
                  {p.sanctioned_amount ? `₹${p.sanctioned_amount.toLocaleString()}` : 'Amount Unknown'}
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
};
