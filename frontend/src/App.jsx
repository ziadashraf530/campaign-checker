import { useRef, useState } from 'react'
import axios from 'axios'

export default function App() {
  const brandRef = useRef(null)
  const fileRef = useRef(null)
  const refImagesRef = useRef(null)
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const run = async () => {
    const brand = brandRef.current ? brandRef.current.value.trim() : 'unknown'
    const targetPath = fileRef.current ? fileRef.current.value.trim() : ''
    const refPath = refImagesRef.current ? refImagesRef.current.value.trim() : ''
    
    setLoading(true)
    setError(null)
    try {
      const payload = {
        brand_name: brand || 'unknown'
      }
      if (targetPath) {
        payload.target_path = targetPath
      }
      if (refPath) {
        payload.reference_path = refPath
      }
      
      const res = await axios.post('http://127.0.0.1:8000/run-analysis/', payload)
      
      const responseResults = res.data.results || [];
      setResults(responseResults)
      
      if (responseResults.length === 0) {
        setError('No posts found to analyze. Please check if the "data" folder exists and has files, or if the provided path is correct.')
      }
    } catch (err) {
      setError('Error: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: 20 }}>
      <h1>Campaign Checker</h1>
      <input ref={brandRef} placeholder="Brand Name" defaultValue="" />
      <input ref={fileRef} placeholder="File or Folder Path (Optional)" style={{ marginLeft: 8, width: 250 }} />
      <input ref={refImagesRef} placeholder="Reference Images Folder (Optional)" style={{ marginLeft: 8, width: 250 }} />
      <button onClick={run} disabled={loading} style={{ marginLeft: 8 }}>
        {loading ? 'Running...' : 'Run'}
      </button>

      {error && <p style={{ color: 'red', marginTop: 10 }}>{error}</p>}

      <table border="1" style={{ marginTop: 20 }}>
        <thead>
          <tr>
            <th>Influencer</th>
            <th>Platform</th>
            <th>File</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => (
            <tr key={i}>
              <td>{r.influencer}</td>
              <td>{r.platform}</td>
              <td>{r.file}</td>
              <td>{r.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
