import { useState, useEffect } from 'react'

// Live system values (KB doc/chunk counts, verifier GPU) from the proxy's
// /api/system-info — set via systemd env on the VPS, so hardware/KB changes
// update the UI without a frontend rebuild. Single source of truth for the
// landing page and the SystemInfo panel.
//
// Returns null until the fetch lands, and stays null if the proxy is
// unreachable — callers decide their own fallback/placeholder.
export default function useSystemInfo() {
  const [info, setInfo] = useState(null)

  useEffect(() => {
    fetch('/api/system-info')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setInfo)
      .catch(err => console.error('useSystemInfo: failed to fetch /api/system-info:', err))
  }, [])

  return info
}
