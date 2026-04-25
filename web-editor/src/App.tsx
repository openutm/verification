import { useEffect, useState } from 'react'
import ScenarioEditor from './components/ScenarioEditor'
import ConfigScreen from './components/ConfigScreen'

const readRoute = () =>
  (typeof globalThis.location !== 'undefined' && globalThis.location.hash === '#/config' ? 'config' : 'editor')

function App() {
  const [route, setRoute] = useState<'editor' | 'config'>(readRoute)

  useEffect(() => {
    const handler = () => setRoute(readRoute())
    globalThis.addEventListener('hashchange', handler)
    return () => globalThis.removeEventListener('hashchange', handler)
  }, [])

  return (
    <div style={{ width: '100vw', height: '100vh' }}>
      {route === 'config' ? <ConfigScreen /> : <ScenarioEditor />}
    </div>
  )
}

export default App
