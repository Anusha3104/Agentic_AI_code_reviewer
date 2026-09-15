import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import api from '../api.js'
import SeverityBadge from '../components/SeverityBadge.jsx'

const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 }

export default function ReviewDetails() {
  const { reviewId } = useParams()
  const [review, setReview] = useState(null)
  const [findings, setFindings] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.getReview(reviewId), api.getReviewFindings(reviewId)])
      .then(([reviewData, findingsData]) => {
        setReview(reviewData)
        setFindings(
          [...findingsData].sort(
            (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]
          )
        )
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [reviewId])

  if (loading) return <p className="subtitle">Loading…</p>
  if (error) return <div className="error-banner">Could not load this review ({error}).</div>
  if (!review) return null

  return (
    <div>
      <h2>Review #{review.id}</h2>
      <p className="subtitle">
        <Link to="/pull-requests">&larr; Back to Pull Requests</Link> — status: {review.status}
      </p>

      <div className="finding-card" style={{ borderLeftColor: 'var(--accent)' }}>
        <h4>Summary</h4>
        <p>{review.summary}</p>
      </div>

      <h3 style={{ marginTop: 28 }}>Findings ({findings.length})</h3>

      {findings.length === 0 ? (
        <div className="empty-state">No high-confidence issues found.</div>
      ) : (
        findings.map((f) => (
          <div key={f.id} className={`finding-card ${f.severity}`}>
            <h4>{f.title}</h4>
            <div className="meta">
              <SeverityBadge severity={f.severity} /> &nbsp;
              {f.category} &nbsp;•&nbsp; <code>{f.file}:{f.line}</code> &nbsp;•&nbsp;
              confidence {Math.round(f.confidence * 100)}% &nbsp;•&nbsp;
              validation: {f.validation_status}
            </div>
            <p><span className="label">Description:</span> {f.description}</p>
            <p><span className="label">Suggestion:</span> {f.suggestion}</p>
          </div>
        ))
      )}
    </div>
  )
}
