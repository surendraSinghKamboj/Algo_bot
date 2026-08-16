import './globals.css'

export const metadata = {
  title: 'Algo Bot Dashboard',
}

export default function RootLayout({ children }){
  return (
    <html lang="en">
      <body>
        <div className="app">
          <aside className="sidebar">
            <h2>Algo Bot</h2>
            <nav>
              <a href="/">Dashboard</a>
              <a href="/positions">Positions</a>
              <a href="/signals">Signals</a>
              <a href="/options">Options</a>
              <a href="/risk">Risk</a>
              <a href="/backtest">Backtest</a>
              <a href="/system">System</a>
            </nav>
          </aside>
          <main className="content">{children}</main>
        </div>
      </body>
    </html>
  )
}
