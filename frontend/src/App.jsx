import { useState } from 'react'
import Landing from './pages/Landing'
import Chat from './pages/Chat'

export default function App() {
  const [page, setPage] = useState('landing')

  return (
    <div className="min-h-screen bg-primary">
      {page === 'landing' ? (
        <Landing onStart={() => setPage('chat')} />
      ) : (
        <Chat onBack={() => setPage('landing')} />
      )}
    </div>
  )
}
