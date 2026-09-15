import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api.js'

export default function PullRequests() {
  const [pullRequests, setPullRequests] = useState([])
  const [repositories, setRepositories] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.listPullRequests(), api.listRepositories()])
      .then(([prs, repos]) => {
        setPullRequests(prs)
        setRepositories(repos)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const repoName = (repositoryId) => {
    const repo = repositories.find((r) => r.id === repositoryId)
    return repo ? `${repo.owner}/${repo.name}` : `#${repositoryId}`
  }

  if (loading) return <p className="subtitle">Loading…</p>

  return (
    <div>
      <h2>Pull Requests</h2>
      <p className="subtitle">All pull requests the reviewer has seen, across every connected repository.</p>

      {error && <div className="error-banner">Could not reach the backend API ({error}).</div>}

      {pullRequests.length === 0 ? (
        <div className="empty-state">No pull requests yet.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Repository</th>
              <th>PR #</th>
              <th>Author</th>
              <th>Status</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {pullRequests.map((pr) => (
              <tr key={pr.id}>
                <td>{repoName(pr.repository_id)}</td>
                <td>
                  <Link to={`/pull-requests/${pr.id}`}>#{pr.github_pr_number}</Link> — {pr.title}
                </td>
                <td>{pr.author}</td>
                <td>{pr.status}</td>
                <td>{new Date(pr.updated_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
