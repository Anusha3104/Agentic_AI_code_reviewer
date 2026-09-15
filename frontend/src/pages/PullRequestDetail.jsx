import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import api from '../api.js'

export default function PullRequestDetail() {
  const { prId } = useParams()
  const [reviews, setReviews] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .getPullRequestReviews(prId)
      .then(setReviews)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [prId])

  if (loading) return <p className="subtitle">Loading…</p>

  return (
    <div>
      <h2>Reviews for Pull Request #{prId}</h2>
      <p className="subtitle">
        <Link to="/pull-requests">&larr; Back to Pull Requests</Link>
      </p>

      {error && <div className="error-banner">Could not load reviews ({error}).</div>}

      {reviews.length === 0 ? (
        <div className="empty-state">No reviews have run for this pull request yet.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Review</th>
              <th>Status</th>
              <th>Summary</th>
              <th>Started</th>
            </tr>
          </thead>
          <tbody>
            {reviews.map((r) => (
              <tr key={r.id}>
                <td><Link to={`/reviews/${r.id}`}>Review #{r.id}</Link></td>
                <td>{r.status}</td>
                <td>{r.summary}</td>
                <td>{new Date(r.started_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
