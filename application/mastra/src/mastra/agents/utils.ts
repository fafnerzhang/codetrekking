const getApiBaseUrl = () => process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8010';
export  { getApiBaseUrl };