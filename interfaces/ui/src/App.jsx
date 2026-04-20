import React, { useState, useEffect } from 'react'
import './index.css'

const API_BASE = 'http://localhost:8001'

function App() {
  const [activeTab, setActiveTab] = useState('screener') // 'screener' or 'workflow'
  const [screenerData, setScreenerData] = useState([])
  const [runDates, setRunDates] = useState([])
  const [selectedDate, setSelectedDate] = useState('')
  const [walterStats, setWalterStats] = useState({ incidents: [], recent_runs: [] })
  const [cliTasks, setCliTasks] = useState([])
  const [activeTasks, setActiveTasks] = useState([])
  const [selectedMarket, setSelectedMarket] = useState('global_full.csv')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    initApp()
  }, [])

  useEffect(() => {
    if (activeTab === 'workflow') {
      fetchActiveTasks()
      const interval = setInterval(fetchActiveTasks, 3000)
      return () => clearInterval(interval)
    }
  }, [activeTab])

  const initApp = async () => {
    setLoading(true)
    try {
      const [runsRes, statsRes, tasksRes] = await Promise.all([
        fetch(`${API_BASE}/screener/runs`),
        fetch(`${API_BASE}/walter/stats`),
        fetch(`${API_BASE}/workflow/tasks`)
      ])
      const runs = await runsRes.json()
      const stats = await statsRes.json()
      const tasks = await tasksRes.json()
      
      setRunDates(runs)
      setWalterStats(stats)
      setCliTasks(tasks)
      
      if (runs.length > 0) {
        setSelectedDate(runs[0]) // Default to latest
      }

      if (activeTab === 'screener' && runs.length > 0) {
         fetchScreenerResults(runs[0])
      }
    } catch (err) {
      console.error('Failed to init app:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchActiveTasks = async () => {
    try {
      const res = await fetch(`${API_BASE}/workflow/active`)
      const data = await res.json()
      setActiveTasks(data)
    } catch (err) {
      console.error('Failed to fetch active tasks:', err)
    }
  }

  const fetchScreenerResults = async (date) => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/screener?run_date=${date}`)
      const data = await res.json()
      setScreenerData(data)
    } catch (err) {
      console.error('Failed to fetch screener results:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div id="root">
      <nav>
        <div className="container flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span style={{ fontWeight: 'bold', fontSize: '1.2rem', letterSpacing: '1px', color: 'var(--text-primary)' }}>
              Global Net-Net Scanner: <span style={{ color: 'var(--text-secondary)', fontWeight: 'normal', fontSize: '0.9rem' }}>An Open Source Project</span>
            </span>
            <div className="flex gap-4" style={{ marginLeft: '2rem' }}>
              <button 
                className={`nav-link ${activeTab === 'screener' ? 'active' : ''}`}
                onClick={() => setActiveTab('screener')}
              >
                SCREENER
              </button>
              <button 
                className={`nav-link ${activeTab === 'workflow' ? 'active' : ''}`}
                onClick={() => setActiveTab('workflow')}
              >
                WORKFLOW
              </button>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-mono text-xs text-secondary">API: ONLINE</span>
            <button className="primary text-xs" onClick={initApp}>REFRESH</button>
          </div>
        </div>
      </nav>

      <main className="container p-4" style={{ flex: 1, minWidth: 'min-content' }}>
        {activeTab === 'screener' ? (
          <ScreenerView 
            data={screenerData} 
            loading={loading} 
            runDates={runDates} 
            selectedDate={selectedDate} 
            onDateChange={setSelectedDate} 
          />
        ) : (
          <WorkflowView 
            stats={walterStats} 
            cliTasks={cliTasks} 
            activeTasks={activeTasks}
            selectedMarket={selectedMarket}
            onMarketChange={setSelectedMarket}
            onTaskStarted={fetchActiveTasks}
          />
        )}
      </main>

      <footer className="p-4 text-center">
        <span className="text-xs text-secondary text-mono">GLOBAL NET-NET SCANNER | WALTER OS v1.0 | OPEN_SOURCE_LICENSE</span>
      </footer>
    </div>
  )
}

function ScreenerView({ data, loading, runDates, selectedDate, onDateChange }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [regionFilter, setRegionFilter] = useState('ALL')
  const [noRedFlags, setNoRedFlags] = useState(false)
  const [passMosOnly, setPassMosOnly] = useState(false)

  if (loading && data.length === 0) return <div className="text-secondary text-mono">LOADING_TRUTH_DATA...</div>

  // Create unique regions list
  const regions = ['ALL', ...new Set(data.map(item => item.country).filter(Boolean))].sort()

  // Filtering Logic
  const filteredData = data.filter(item => {
    const matchesSearch = 
      item.ticker?.toLowerCase().includes(searchTerm.toLowerCase()) || 
      item.name?.toLowerCase().includes(searchTerm.toLowerCase())
    
    const matchesRegion = regionFilter === 'ALL' || item.country === regionFilter
    const matchesNoRedFlags = !noRedFlags || (item.red_flags || []).length === 0
    const matchesPassMos = !passMosOnly || item.passes_price_to_ncav_rule === true

    return matchesSearch && matchesRegion && matchesNoRedFlags && matchesPassMos
  })

  const formatPct = (val) => {
    if (val === null || val === undefined) return '-'
    const num = val * 100
    const color = num > 0 ? 'var(--success)' : num < 0 ? 'var(--danger)' : 'inherit'
    return <span style={{ color }}>{num > 0 ? '+' : ''}{num.toFixed(1)}%</span>
  }

  const formatVal = (val, dec = 2) => {
    if (val === null || val === undefined) return '-'
    return val.toFixed(dec)
  }

  return (
    <div className="flex flex-col gap-0">
      {/* Header Container */}
      <div className="glass-panel" style={{ padding: '1rem', borderBottom: 'none', borderRadius: '8px 8px 0 0' }}>
        <div className="flex justify-between items-center">
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Net-Nets: Deep-Value Securities Trading Below Net Current Asset Value</h2>
          
          <div className="flex flex-col items-end gap-1">
            <div className="flex items-center gap-2">
              <label className="text-xs text-secondary text-mono">SNAPSHOT:</label>
              <select 
                className="filter-select"
                value={selectedDate} 
                onChange={(e) => onDateChange(e.target.value)}
              >
                {runDates.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
            <span className="text-mono text-xs text-secondary">
              {loading ? 'SYNCING...' : `${filteredData.length} / ${data.length} ASSETS_SHOWN`}
            </span>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="filter-bar">
        <div className="filter-group">
          <input 
            type="text" 
            placeholder="Search Ticker/Name..." 
            className="search-input"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="filter-group">
          <label className="text-xs text-secondary text-mono">REGION:</label>
          <select 
            className="filter-select"
            value={regionFilter}
            onChange={(e) => setRegionFilter(e.target.value)}
          >
            {regions.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>

        <div className="filter-group" style={{ marginLeft: 'auto' }}>
          <label className="checkbox-toggle">
            <input 
              type="checkbox" 
              checked={noRedFlags}
              onChange={(e) => setNoRedFlags(e.target.checked)}
            />
            NO_RED_FLAGS
          </label>

          <label className="checkbox-toggle" style={{ marginLeft: '1rem' }}>
            <input 
              type="checkbox" 
              checked={passMosOnly}
              onChange={(e) => setPassMosOnly(e.target.checked)}
            />
            PASS_MOS_ONLY
          </label>
        </div>
      </div>
      
      <div className="table-container" style={{ borderRadius: '0 0 8px 8px' }}>
        <table>
          <thead>
            <tr>
              <th>ASSET</th>
              <th>NAME</th>
              <th>REGION</th>
              <th>FS_DATE</th>
              <th>CURR</th>
              <th>MoS Check</th>
              <th>NCAV_PS</th>
              <th>MOS %</th>
              <th>PRICE/NCAV</th>
              <th>CR</th>
              <th>D/E</th>
              <th title="NCAV Change QoQ">Q_QoQ</th>
              <th title="NCAV Change HoH">Q_HoH</th>
              <th title="NCAV Change YoY">Q_YoY</th>
              <th title="Dilution QoQ">D_QoQ</th>
              <th title="Dilution HoH">D_HoH</th>
              <th title="Dilution YoY">D_YoY</th>
              <th>INSIDER</th>
              <th>FLAGS</th>
            </tr>
          </thead>
          <tbody>
            {filteredData.map((row, idx) => (
              <tr key={idx} style={{ opacity: loading ? 0.5 : 1 }}>
                <td className="text-mono" style={{ color: 'var(--accent-primary)', whiteSpace: 'nowrap' }}>{row.ticker}</td>
                <td style={{ fontSize: '0.75rem', opacity: 0.8, maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.name}>
                  {row.name}
                </td>
                <td className="text-xs">{row.country}</td>
                <td className="text-mono text-xs">{row.fs_date}</td>
                <td className="text-mono text-xs">{row.currency}</td>
                <td>
                  {row.passes_price_to_ncav_rule && (
                    <span className="badge badge-pass">PASS</span>
                  )}
                </td>
                <td className="text-mono">{formatVal(row.ncav_ps)}</td>
                <td className="text-mono" style={{ color: row.margin_of_safety > 0.3 ? 'var(--success)' : 'inherit' }}>
                  {formatVal(row.margin_of_safety * 100, 1)}%
                </td>
                <td className="text-mono">{formatVal(row.price_to_ncav)}</td>
                <td className="text-mono text-xs">{formatVal(row.current_ratio, 1)}</td>
                <td className="text-mono text-xs">{formatVal(row.debt_to_equity, 1)}</td>
                <td className="text-mono text-xs">{formatPct(row.ncav_change_qoq)}</td>
                <td className="text-mono text-xs">{formatPct(row.ncav_change_hoh)}</td>
                <td className="text-mono text-xs">{formatPct(row.ncav_change_yoy)}</td>
                <td className="text-mono text-xs">{formatPct(row.dilution_qoq)}</td>
                <td className="text-mono text-xs">{formatPct(row.dilution_hoh)}</td>
                <td className="text-mono text-xs">{formatPct(row.dilution_yoy)}</td>
                <td>
                  {row.insider_signal && row.insider_signal !== 'None' && (
                    <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.1)', color: '#38bdf8', border: '1px solid #38bdf8', whiteSpace: 'nowrap' }}>
                      {row.insider_signal}
                    </span>
                  )}
                </td>
                <td style={{ minWidth: '100px' }}>
                  <div className="flex gap-1 flex-wrap">
                    {row.green_flags.map((f, i) => <span key={i} title={f} style={{ color: 'var(--success)', fontSize: '0.6rem' }}>●</span>)}
                    {row.red_flags.map((f, i) => <span key={i} title={f} style={{ color: 'var(--danger)', fontSize: '0.6rem' }}>▲</span>)}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function WorkflowView({ stats, cliTasks, activeTasks, selectedMarket, onMarketChange, onTaskStarted }) {
  const [logs, setLogs] = useState([])
  const [streamingPid, setStreamingPid] = useState(null)

  const markets = [
    { label: 'GLOBAL', value: 'global_full.csv' },
    { label: 'UNITED STATES', value: 'us_full.csv' },
    { label: 'HONG KONG', value: 'hk_full.csv' },
    { label: 'JAPAN', value: 'jp_full.csv' },
    { label: 'THAILAND', value: 'th_full.csv' }
  ]
  
  const runTask = async (mode, taskType = 'cycle', args = {}) => {
    const label = taskType === 'cycle' ? `WALTER_${mode.toUpperCase()}_CYCLE` : `CLI_${mode.toUpperCase()}`
    setLogs([`>>> STARTING ${label}`])
    
    // Discover supported arguments from metadata
    const taskMeta = cliTasks.find(t => t.name === mode)
    const supportedArgs = taskMeta?.supported_args || []

    // Default args for certain tasks
    const finalArgs = { ...args }
    if (taskType === 'direct') {
      // Intelligent injector: only pass arguments that the script explicitly defines
      if (supportedArgs.includes('csv')) {
        if (!finalArgs.csv) finalArgs.csv = `data/tickers/${selectedMarket}`
      } else if (supportedArgs.includes('tickers_csv')) {
        if (!finalArgs.tickers_csv) finalArgs.tickers_csv = `data/tickers/${selectedMarket}`
      } else if (supportedArgs.includes('shortlist')) {
        // If the script targets a shortlist but we have a market selected, 
        // we might still want to pass the universe file if the script is flexible, 
        // but usually 'shortlist' expects a different format. 
        // For now, we only inject if explicitly supported.
        if (!finalArgs.shortlist && selectedMarket !== 'global_full.csv') {
           // Mapping selected market to a potential regional shortlist is complex, 
           // but we can pass the universe path as the 'shortlist' if the script allows it.
           // finalArgs.shortlist = `data/tickers/${selectedMarket}`
        }
      }
    }
    if (taskType === 'cycle' && mode === 'weekly') {
      finalArgs.ncav_regional = true
    }

    try {
      const res = await fetch(`${API_BASE}/workflow/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, task_type: taskType, args: finalArgs })
      })
      const data = await res.json()
      onTaskStarted()
      attachToLogStream(data.pid, label)
    } catch (err) {
      setLogs(prev => [...prev, `ERROR: ${err.message}`])
    }
  }

  const killTask = async (pid) => {
    try {
      await fetch(`${API_BASE}/workflow/kill/${pid}`, { method: 'POST' })
      setLogs(prev => [...prev, `<<< KILL_SIGNAL_SENT [PID: ${pid}]`])
    } catch (err) {
      console.error('Failed to kill task:', err)
    }
  }

  const attachToLogStream = (pid, label) => {
    setStreamingPid(pid)
    setLogs(prev => [...prev, `--- ATTACHED_TO_STREAM [PID: ${pid}] ---`])
    const ws = new WebSocket(`ws://localhost:8001/workflow/stream/${pid}`)
    ws.onmessage = (event) => {
      setLogs(prev => [...prev.slice(-200), event.data])
    }
    ws.onclose = () => {
      setLogs(prev => [...prev, `<<< ${label || 'PROCESS'} FINISHED`])
      setStreamingPid(null)
    }
  }

  return (
    <div className="flex flex-col gap-4" style={{ height: 'calc(100vh - 200px)' }}>
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <h2 style={{ margin: 0 }}>WORKFLOW_CONTROL_CENTER</h2>
          <div className="flex items-center gap-2 ml-4 p-1 px-3 glass-panel" style={{ border: '1px solid #333' }}>
            <label className="text-xs text-secondary text-mono">TARGET_MARKET:</label>
            <select 
              className="filter-select"
              style={{ background: 'transparent', border: 'none', color: 'var(--accent-primary)', fontWeight: 'bold' }}
              value={selectedMarket}
              onChange={(e) => onMarketChange(e.target.value)}
            >
              {markets.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>
        </div>
        <div className="flex gap-4">
          <button className="primary" onClick={() => runTask('daily')}>RUN_DAILY_CYCLE</button>
          <button className="primary" onClick={() => runTask('weekly')}>RUN_WEEKLY_CYCLE</button>
        </div>
      </div>

      <div className="flex gap-4" style={{ flex: 1, minHeight: 0 }}>
        {/* Left Panel: Tasks Grid */}
        <div className="flex flex-col gap-4" style={{ flex: 1.5, overflowY: 'auto' }}>
          {/* Core Pipeline Section */}
          <div className="mb-4">
            <h3 className="text-xs text-secondary text-mono mb-3 flex items-center gap-2">
              <span style={{ color: 'var(--accent-primary)' }}>▶</span> CORE_PIPELINE
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {cliTasks.filter(t => t.group === 'CORE PIPELINE').map(task => {
                const active = activeTasks.find(t => t.mode === task.name && t.task_type === 'direct')
                return (
                  <div key={task.name} className={`task-card ${active ? 'active' : ''}`} style={{ borderLeft: '3px solid var(--accent-primary)' }}>
                    <div className="flex justify-between items-start mb-2">
                      <span className="task-name" style={{ fontSize: '0.85rem' }}>{task.label}</span>
                      {active ? (
                        <span className="badge badge-run">RUNNING</span>
                      ) : (
                        <span className="badge badge-idle">IDLE</span>
                      )}
                    </div>
                    <div className="text-xs text-secondary mb-4 opacity-70" style={{ lineHeight: '1.4' }}>
                      {task.description.split(/(\[.*?\])/).map((part, i) => 
                        part.startsWith('[') ? <b key={i} style={{ color: part.includes('Required') ? 'var(--danger)' : 'var(--accent-primary)' }}>{part}</b> : part
                      )}
                    </div>
                    <div className="flex gap-2">
                      {!active ? (
                        <button className="text-xs p-1 px-3" onClick={() => runTask(task.name, 'direct')}>RUN_TASK</button>
                      ) : (
                        <>
                          <button className="text-xs p-1 px-3 secondary" onClick={() => attachToLogStream(active.pid, `CLI_${task.name.toUpperCase()}`)}>ATTACH</button>
                          <button className="text-xs p-1 px-3 danger" onClick={() => killTask(active.pid)}>KILL</button>
                        </>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Utilities Section */}
          <div className="opacity-80">
            <h3 className="text-xs text-secondary text-mono mb-3">ADDITIONAL_UTILITIES</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {cliTasks.filter(t => t.group !== 'CORE PIPELINE').map(task => {
                const active = activeTasks.find(t => t.mode === task.name && t.task_type === 'direct')
                return (
                  <div key={task.name} className={`task-card ${active ? 'active' : ''}`}>
                    <div className="flex justify-between items-start mb-2">
                      <span className="task-name">{task.name}</span>
                      {active ? (
                        <span className="badge badge-run">RUNNING</span>
                      ) : (
                        <span className="badge badge-idle">IDLE</span>
                      )}
                    </div>
                    <div className="text-xs text-secondary mb-4 opacity-70">
                      {task.description}
                    </div>
                    <div className="flex gap-2">
                      {!active ? (
                        <button className="text-xs p-1 px-3" onClick={() => runTask(task.name, 'direct')}>RUN_TASK</button>
                      ) : (
                        <>
                          <button className="text-xs p-1 px-3 secondary" onClick={() => attachToLogStream(active.pid, `CLI_${task.name.toUpperCase()}`)}>ATTACH</button>
                          <button className="text-xs p-1 px-3 danger" onClick={() => killTask(active.pid)}>KILL</button>
                        </>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Right Panel: Console & Status */}
        <div className="flex flex-col gap-4" style={{ flex: 2 }}>
          <div className="glass-panel" style={{ flex: 2, display: 'flex', flexDirection: 'column', background: '#000', border: '1px solid #333' }}>
            <div className="flex justify-between items-center mb-2 pb-2" style={{ borderBottom: '1px solid #222' }}>
              <span className="text-mono text-xs text-secondary">TERMINAL_CONSOLE [PID: {streamingPid || 'NONE'}]</span>
              <button className="text-xs" onClick={() => setLogs([])} style={{ height: '24px', padding: '0 8px' }}>CLEAR</button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: '#10b981', lineHeight: '1.4' }}>
              {logs.map((line, i) => <div key={i}>{line}</div>)}
            </div>
          </div>

          <div className="flex gap-4" style={{ flex: 1 }}>
            <div className="glass-panel" style={{ flex: 1 }}>
              <h3 className="text-sm text-mono mb-2">OPEN_INCIDENTS</h3>
              <div className="flex flex-col gap-2 overflow-y-auto" style={{ maxHeight: '150px' }}>
                {stats.incidents.map((inc, i) => (
                  <div key={i} className="text-xs p-2" style={{ border: '1px solid var(--danger)', borderRadius: '4px', background: 'rgba(239, 68, 68, 0.05)' }}>
                    <div className="flex justify-between">
                      <span className="text-mono" style={{ color: 'var(--danger)' }}>{inc.signature}</span>
                    </div>
                    <div>{inc.title}</div>
                  </div>
                ))}
                {stats.incidents.length === 0 && <div className="text-xs text-secondary">NO_OPEN_INCIDENTS</div>}
              </div>
            </div>
            
            <div className="glass-panel" style={{ flex: 1 }}>
              <h3 className="text-sm text-mono mb-2">ACTIVE_PROCESSES</h3>
              <div className="flex flex-col gap-1 overflow-y-auto" style={{ maxHeight: '150px' }}>
                {activeTasks.map((run, i) => (
                  <div key={i} className="text-xs flex justify-between items-center p-1" style={{ borderBottom: '1px solid #222' }}>
                    <span className="text-mono">{run.mode}</span>
                    <span className="text-secondary" style={{ fontSize: '0.6rem' }}>PID: {run.pid}</span>
                  </div>
                ))}
                {activeTasks.length === 0 && <div className="text-xs text-secondary">NO_ACTIVE_TASKS</div>}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
