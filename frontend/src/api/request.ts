import axios from 'axios'

export const request = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// ── Response interceptor: handle 403/401 gracefully ──
request.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 403) {
      // Permission denied — let the calling code handle the message
    }
    return Promise.reject(error)
  },
)
