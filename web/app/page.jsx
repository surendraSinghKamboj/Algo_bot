"use client"
import React, {useEffect, useState} from 'react'

function Stat({label, value}){
  return <div className="card"><div className="sub">{label}</div><div className="stat">{value}</div></div>
}

export default function Page(){
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  async function load(){
    setLoading(true)
    try{
      const res = await fetch('http://localhost:8000/dashboard/state')
      if(!res.ok) throw new Error('Failed to fetch')
      setData(await res.json())
    }catch(e){ setError(e.message) }
    finally{ setLoading(false) }
  }

  useEffect(()=>{ load(); const id=setInterval(load,3000); return ()=>clearInterval(id)},[])

  if(loading) return <div className="card">Loading...</div>
  if(error) return <div className="card">Error: {error}</div>
  if(!data) return <div className="card">No data</div>

  const m = data.market || {}
  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:12}}>
        <div>
          <span className={data.trading_mode === 'PAPER' ? 'badge-paper':'badge-live'}>{data.trading_mode}</span>
          <span className='small' style={{marginLeft:12}}>Broker: {data.broker_connected ? 'Connected':'Disconnected'}</span>
        </div>
        <div className='small'>{new Date().toLocaleString()}</div>
      </div>

      <div className='grid'>
        <Stat label="NIFTY" value={m['NIFTY']} />
        <Stat label="BANKNIFTY" value={m['BANKNIFTY']} />
        <Stat label="India VIX" value={m['India VIX']} />
        <Stat label="Gold" value={m['Gold']} />
        <Stat label="Silver" value={m['Silver']} />
        <Stat label="Crude" value={m['Crude']} />
        <Stat label="USDINR" value={m['USDINR']} />
        <div className='card'><div className='sub'>Regime</div><div className='stat'>{data.regime} <span className='small'>({data.risk})</span></div></div>
      </div>

      <div className='grid' style={{marginTop:12}}>
        <div className='card'><div className='sub'>Signal</div><div className='stat'>{data.signal}</div><div className='small'>{data.no_trade_reason}</div></div>
        <div className='card'><div className='sub'>Portfolio Equity</div><div className='stat'>—</div><div className='small'>Realized / Unrealized: —</div></div>
        <div className='card'><div className='sub'>Drawdown</div><div className='stat'>{data.drawdown}</div></div>
        <div className='card'><div className='sub'>Margin Utilization</div><div className='stat'>{data.margin_utilization}</div></div>
      </div>

      <div className='card' style={{marginTop:12}}>
        <h3>Positions</h3>
        {(!data.positions || data.positions.length===0) ? <div className='small'>No positions</div> : (
          <table className='table'><thead><tr><th>Instrument</th><th>Qty</th><th>PnL</th></tr></thead>
            <tbody>{data.positions.map((p,i)=>(<tr key={i}><td>{p.instrument}</td><td>{p.qty}</td><td>{p.pnl}</td></tr>))}</tbody></table>
        )}
      </div>
    </div>
  )
}
