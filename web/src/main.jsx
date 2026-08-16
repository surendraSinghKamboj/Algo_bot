import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import Dashboard from './views/Dashboard'
import Positions from './views/Positions'
import Signals from './views/Signals'
import Options from './views/Options'
import Risk from './views/Risk'
import Backtest from './views/Backtest'
import System from './views/System'
import './styles.css'

function App(){
  return (
    <BrowserRouter>
      <div className="app">
        <nav className="sidebar">
          <h2>Algo Bot</h2>
          <Link to="/">Dashboard</Link>
          <Link to="/positions">Positions</Link>
          <Link to="/signals">Signals</Link>
          <Link to="/options">Options</Link>
          <Link to="/risk">Risk</Link>
          <Link to="/backtest">Backtest</Link>
          <Link to="/system">System</Link>
        </nav>
        <main className="content">
          <Routes>
            <Route path="/" element={<Dashboard/>} />
            <Route path="/positions" element={<Positions/>} />
            <Route path="/signals" element={<Signals/>} />
            <Route path="/options" element={<Options/>} />
            <Route path="/risk" element={<Risk/>} />
            <Route path="/backtest" element={<Backtest/>} />
            <Route path="/system" element={<System/>} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

createRoot(document.getElementById('root')).render(<App />)
