import { HashRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import PullRequests from './pages/PullRequests.jsx'
import PullRequestDetail from './pages/PullRequestDetail.jsx'
import ReviewDetails from './pages/ReviewDetails.jsx'

export default function App() {
  return (
    <HashRouter>
      <div className="app-shell">
        <aside className="sidebar">
          <h1>🤖 Code Reviewer</h1>
          <nav>
            <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : '')}>
              Dashboard
            </NavLink>
            <NavLink to="/pull-requests" className={({ isActive }) => (isActive ? 'active' : '')}>
              Pull Requests
            </NavLink>
          </nav>
        </aside>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/pull-requests" element={<PullRequests />} />
            <Route path="/pull-requests/:prId" element={<PullRequestDetail />} />
            <Route path="/reviews/:reviewId" element={<ReviewDetails />} />
          </Routes>
        </main>
      </div>
    </HashRouter>
  )
}
