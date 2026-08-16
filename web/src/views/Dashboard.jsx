import React, {useEffect, useState} from 'react'

function KeyValue({label, value}){
  return <div className="card"><div className="sub">{label}</div><div className="stat">{value}</div></div>
}

export default function Dashboard(){
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  async function fetchState(){
    setLoading(true)
    try{
      const res = await fetch('/dashboard/state')
      if(!res.ok) throw new Error('Failed to fetch')
      const data = await res.json()
      setState(data)
    }catch(err){
      setError(err.message)
    }finally{setLoading(false)}
  }

  useEffect(()=>{fetchState(); const id = setInterval(fetchState, 3000); return ()=>clearInterval(id)},[])

  if(loading) return <div className="card">Loading dashboard...</div>
  if(error) return <div className="card">Error: {error}</div>
  if(!state) return <div className="card">No data</div>

  const market = state.market || {}
  const positions = state.positions || []
  return (
    <div>
      <div className="header">
        <div>
          <span className={state.trading_mode === 'PAPER' ? 'badge-paper' : 'badge-live'}>{state.trading_mode}</span>
          <span style={{marginLeft:12}} className="small">Broker: {state.broker_connected ? 'Connected':'Disconnected'}</span>
        </div>
        <div>{new Date().toLocaleString()}</div>
      </div>

      <div className="grid">
        <KeyValue label="NIFTY" value={market['NIFTY']}/>
        <KeyValue label="BANKNIFTY" value={market['BANKNIFTY']}/>
        <KeyValue label="India VIX" value={market['India VIX']}/>
        <KeyValue label="Gold" value={market['Gold']}/>
        <KeyValue label="Silver" value={market['Silver']}/>
        <KeyValue label="Crude" value={market['Crude']}/>
        <KeyValue label="USDINR" value={market['USDINR']}/>
        <div className="card">
          <div className="sub">Regime</div>
          <div className="stat">{state.regime} <span className="small">({state.risk})</span></div>
        </div>
      </div>

      <div className="grid" style={{marginTop:12}}>
        <div className="card">
          <div className="sub">Signal</div>
          <div className="stat">{state.signal}</div>
          <div className="small">{state.no_trade_reason}</div>
        </div>
        <div className="card">
          <div className="sub">Portfolio Equity</div>
          <div className="stat">{state.risk ? ("₹" + (state.risk * 100000).toFixed(2)) : '—'}</div>
          <div className="small">Realized / Unrealized: Placeholder</div>
        </div>
        <div className="card">
          <div className="sub">Drawdown</div>
          <div className="stat">{state.drawdown}</div>
        </div>
        <div className="card">
          <div className="sub">Margin Utilization</div>
          <div className="stat">{state.margin_utilization}</div>
        </div>
      </div>

      <div className="card" style={{marginTop:12}}>
        <h3>Positions</h3>
        {positions.length === 0 ? <div className="small">No positions</div> : (
          <table className="table">
            <thead><tr><th>Instrument</th><th>Qty</th><th>PnL</th></tr></thead>
            <tbody>
              {positions.map((p,i)=>(<tr key={i}><td>{p.instrument}</td><td>{p.qty}</td><td>{p.pnl}</td></tr>))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
