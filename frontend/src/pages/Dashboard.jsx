import { useEffect, useState } from 'react'
import api from '../api.js'

export default function Dashboard() {
  const [repositories, setRepositories] = useState([])
  const [pullRequests, setPullRequests] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.listRepositories(), api.listPullRequests()])
      .then(([repos, prs]) => {
        setRepositories(repos)
        setPullRequests(prs)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="subtitle">Loading…</p>

  return (
    <div>
      <h2>Dashboard</h2>
      <p className="subtitle">
        Overview of repositories, pull requests, and reviews tracked by the Agentic AI Code Reviewer.
      </p>

      {error && (
        <div className="error-banner">
          Could not reach the backend API ({error}). Is it running at{' '}
          <code>{import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}</code>?
        </div>
      )}

      <div className="stat-grid">
        <StatCard label="Total repositories" value={repositories.length} />
        <StatCard label="Total pull requests" value={pullRequests.length} />
        <StatCard
          label="Open pull requests"
          value={pullRequests.filter((pr) => pr.status === 'open').length}
        />
      </div>

      {repositories.length === 0 && pullRequests.length === 0 && !error && (
        <div className="empty-state">
          No data yet. Once your GitHub App is installed and a PR is opened
          (or you POST a test webhook payload), reviews will start showing up here.
          <br />
          In the meantime, try the local CLI: <code>python review.py --repo ./test-repository --diff ./test.diff</code>
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value }) {
  return (
    <div className="stat-card">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
    </div>
  )
}
