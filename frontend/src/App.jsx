import { useEffect, useState } from 'react'

function App(){
  const [backendStatus, setBackendStatus] = useState('Checking backend...')
    
  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/health')
      .then((response) => response.json())
      .then((data) => {
        setBackendStatus(data.status)
      })
      .catch(() => {
        setBackendStatus('Backend is not reachable')
      })
    }, [])


    return (
        <div>
        <h1>AWS Cloud Cost Optimizer</h1>
        <p>Cloud cost and utilization analysis platform</p>
        <p>{backendStatus}</p>
        </div>
    )
}
export default App