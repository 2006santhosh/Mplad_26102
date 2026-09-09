import axios from 'axios';

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000',
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('role');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const login = async (credentials: any) => {
  const res = await api.post('/auth/login', credentials);
  if (res.data && res.data.access_token) {
    localStorage.setItem('token', res.data.access_token);
    localStorage.setItem('role', res.data.role);
  }
  return res.data;
};

export const logout = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('role');
  window.location.href = '/login';
};

export const getProjects = async () => {
  const res = await api.get('/api/projects');
  return res.data;
};

export const getProjectDetails = async (id: number) => {
  const res = await api.get(`/api/projects/${id}`);
  return res.data;
};

export const runRiskAssessment = async (id: number) => {
  const res = await api.get(`/api/projects/${id}/risk`);
  return res.data;
};

export const getRiskHistory = async (id: number) => {
  const res = await api.get(`/api/projects/${id}/risk/history`);
  return res.data;
};

export const getTrends = async (id: number) => {
  const res = await api.get(`/api/trends/${id}`);
  return res.data;
};

export const getEarlyWarnings = async (id: number) => {
  const res = await api.get(`/api/projects/${id}/early-warning/`);
  return res.data;
};

export const assessEarlyWarnings = async (id: number) => {
  const res = await api.post(`/api/projects/${id}/early-warning/assess`);
  return res.data;
};

export const getProjectedCompletion = async (id: number) => {
  const res = await api.get(`/api/projected-completion/${id}`);
  return res.data;
};

export const getComparison = async (id: number) => {
  const res = await api.get(`/api/projects/${id}/comparison/`);
  return res.data;
};

export const getSpatialClusters = async () => {
  const res = await api.get('/api/gis/clusters');
  return res.data;
};

export const getReviews = async (id: number) => {
  const res = await api.get(`/api/projects/${id}/review/`);
  return res.data;
};

export const postReview = async (id: number, data: any) => {
  const res = await api.post(`/api/projects/${id}/review/`, data);
  return res.data;
};

export const getDashboardStats = async () => {
  const res = await api.get('/api/dashboard/stats');
  return res.data;
};

export const runPreSanction = async (data: any) => {
  const res = await api.post('/api/pre-sanction/', data);
  return res.data;
};

export const assessCompliance = async (projectId: number) => {
  const response = await api.post(`/api/projects/${projectId}/compliance/assess`);
  return response.data;
};

export const getCompliance = async (projectId: number) => {
  const response = await api.get(`/api/projects/${projectId}/compliance/`);
  return response.data;
};

export const getComplianceHistory = async (projectId: number) => {
  const response = await api.get(`/api/projects/${projectId}/compliance/history`);
  return response.data;
};

export const getPredictiveCompletionRisk = async (projectId: number) => {
  const response = await api.get(`/api/projects/${projectId}/predictive-completion`);
  return response.data;
};

export const assessPredictiveCompletionRisk = async (projectId: number) => {
  const response = await api.post(`/api/projects/${projectId}/predictive-completion/assess`);
  return response.data;
};

export default api;
