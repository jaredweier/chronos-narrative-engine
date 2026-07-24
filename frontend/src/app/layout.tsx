import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Chronos Narrative Engine",
  description: "Next-Gen Police RMS & Narrative Engine",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="app-container">
          <aside className="sidebar">
            <h2 style={{ padding: '0 16px', color: '#fff', fontSize: '20px', marginBottom: '20px' }}>
              Chronos<span style={{color: 'var(--accent-primary)'}}>.</span>
            </h2>
            <nav style={{display: 'flex', flexDirection: 'column', gap: '8px'}}>
              <a href="#" className="sidebar-item active">Dashboard</a>
              <a href="#" className="sidebar-item">Report Gen</a>
              <a href="/investigations" className="sidebar-item">Case Briefs</a>
              <a href="/coaching" className="sidebar-item">Coaching Insights</a>
              <a href="/redact-document" className="sidebar-item">Smart Redaction</a>
              <a href="/audit" className="sidebar-item">AI Audit Trail</a>
              <a href="/review" className="sidebar-item">Review Queue</a>
              <a href="#" className="sidebar-item">Evidence Locker</a>
              <a href="#" className="sidebar-item">Settings</a>
            </nav>
          </aside>
          <main className="main-content">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
