const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function request(path) {
  const res = await fetch(`${API_BASE_URL}${path}`)
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`API error ${res.status}: ${body}`)
  }
  return res.json()
}

export const api = {
  health: () => request('/api/health'),
  listRepositories: () => request('/api/repositories'),
  listPullRequests: () => request('/api/pull-requests'),
  getReview: (reviewId) => request(`/api/reviews/${reviewId}`),
  getReviewFindings: (reviewId) => request(`/api/reviews/${reviewId}/findings`),
  getPullRequestReviews: (prId) => request(`/api/pull-requests/${prId}/reviews`),
}

export default api
