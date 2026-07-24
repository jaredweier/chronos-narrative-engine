"use client";

import { useState } from "react";

interface ElementCheck {
  element: string;
  met: boolean;
  evidence: string;
}

interface StatuteResult {
  statute_code: string;
  is_satisfied: boolean;
  elements_checked: ElementCheck[];
  override_warning?: string;
  error?: string;
}

const MOCK_REPORTS = [
  {
    id: "INC-2026-003",
    title: "Burglary at 100 Main St",
    statute_codes: ["943.10(1)"],
    narrative: "On 07/23/2026 I responded to 100 Main St for a burglary. The victim stated someone entered their garage without permission and took a bicycle. The side door was forced open. I located the suspect, John Doe, riding the bicycle down the street. Doe admitted to breaking into the garage to steal the bike."
  },
  {
    id: "INC-2026-004",
    title: "Theft at Target",
    statute_codes: ["943.20(1)"],
    narrative: "Suspect was seen putting items in his pocket at Target and leaving without paying. Store security stopped him outside. We arrested him for retail theft."
  }
];

export default function ReviewQueuePage() {
  const [selectedReport, setSelectedReport] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<StatuteResult[]>([]);
  const [error, setError] = useState("");
  const [submitStatus, setSubmitStatus] = useState("");

  const verifyStatutes = async () => {
    if (!selectedReport) return;
    
    setLoading(true);
    setError("");
    setResults([]);
    
    try {
      const token = localStorage.getItem("chronos_token") || "";
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/verify-statute`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          narrative: selectedReport.narrative,
          statute_codes: selectedReport.statute_codes
        })
      });

      if (!res.ok) throw new Error("Failed to verify statutes");
      
      const data = await res.json();
      setResults(data.results);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitToSupervisor = () => {
    const hasWarnings = results.some(r => !r.is_satisfied);
    if (hasWarnings) {
      const confirmOverride = window.confirm("WARNING: The AI check found missing legal elements. Submitting now risks a supervisor kickback. Are you sure you want to override and submit?");
      if (!confirmOverride) return;
    }
    setSubmitStatus(`Report ${selectedReport.id} successfully submitted to supervisor queue.`);
    setTimeout(() => {
      setSelectedReport(null);
      setResults([]);
      setSubmitStatus("");
    }, 3000);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto min-h-screen flex flex-col font-sans">
      <h1 className="text-3xl font-bold mb-2">Review Queue</h1>
      <p className="text-gray-600 mb-6">Review your draft reports and verify legal elements before supervisor submission.</p>

      {submitStatus && (
        <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4 font-medium">
          {submitStatus}
        </div>
      )}
      
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4 font-medium">
          {error}
        </div>
      )}

      <div className="flex flex-col md:flex-row gap-6 flex-1 min-h-0">
        {/* Left Side: Queue List */}
        <div className="w-full md:w-1/3 flex flex-col gap-4">
          <div className="bg-white p-4 border rounded shadow-sm flex-1">
            <h2 className="font-semibold text-lg mb-4 border-b pb-2">Pending Drafts</h2>
            <div className="space-y-3">
              {MOCK_REPORTS.map(report => (
                <div 
                  key={report.id}
                  onClick={() => {
                    setSelectedReport(report);
                    setResults([]);
                    setError("");
                  }}
                  className={`p-3 border rounded cursor-pointer transition ${selectedReport?.id === report.id ? 'bg-blue-50 border-blue-400 shadow-sm' : 'hover:bg-gray-50'}`}
                >
                  <div className="font-bold text-gray-800">{report.id}</div>
                  <div className="text-sm text-gray-600">{report.title}</div>
                  <div className="mt-2 text-xs font-mono bg-gray-200 inline-block px-1 rounded">
                    Statutes: {report.statute_codes.join(", ")}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Side: Verification Panel */}
        <div className="w-full md:w-2/3 flex flex-col gap-4">
          {!selectedReport ? (
            <div className="bg-white border rounded shadow-sm flex-1 flex items-center justify-center text-gray-400 italic">
              Select a report from the queue to review
            </div>
          ) : (
            <div className="bg-white border rounded shadow-sm flex-1 flex flex-col">
              <div className="bg-gray-50 border-b p-4 flex justify-between items-center">
                <h2 className="font-semibold text-lg">Reviewing: {selectedReport.id}</h2>
                <div className="flex gap-2">
                  <button 
                    onClick={verifyStatutes}
                    disabled={loading}
                    className="bg-indigo-600 text-white px-4 py-2 text-sm font-medium rounded hover:bg-indigo-700 disabled:opacity-50 transition"
                  >
                    {loading ? "Analyzing..." : "1. Run AI Legal Check"}
                  </button>
                  <button 
                    onClick={handleSubmitToSupervisor}
                    disabled={loading || results.length === 0}
                    className="bg-green-600 text-white px-4 py-2 text-sm font-medium rounded hover:bg-green-700 disabled:opacity-50 transition"
                  >
                    2. Submit to Supervisor
                  </button>
                </div>
              </div>
              
              <div className="p-4 flex-1 overflow-y-auto h-[500px]">
                <div className="mb-6">
                  <h3 className="font-bold text-gray-700 mb-2">Narrative Text</h3>
                  <div className="bg-gray-100 p-3 rounded font-mono text-sm whitespace-pre-wrap">
                    {selectedReport.narrative}
                  </div>
                </div>

                {results.length > 0 && (
                  <div>
                    <h3 className="font-bold text-gray-700 mb-3 border-b pb-1">AI Statute Verification Results</h3>
                    
                    {results.map((res, i) => (
                      <div key={i} className="mb-6 bg-white border rounded shadow-sm overflow-hidden">
                        <div className={`p-3 font-bold flex items-center justify-between ${res.is_satisfied ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                          <span>Statute {res.statute_code}</span>
                          <span>{res.is_satisfied ? "✓ SATISFIED" : "⚠ INCOMPLETE"}</span>
                        </div>
                        
                        {res.error ? (
                          <div className="p-4 text-red-600 italic">{res.error}</div>
                        ) : (
                          <div className="p-0">
                            {!res.is_satisfied && res.override_warning && (
                              <div className="p-3 bg-red-50 border-b border-red-100 text-sm font-semibold text-red-700">
                                🛑 WARNING: {res.override_warning}
                              </div>
                            )}
                            
                            <table className="w-full text-sm text-left">
                              <thead className="bg-gray-50 border-b">
                                <tr>
                                  <th className="p-3 w-10">Status</th>
                                  <th className="p-3 w-1/3">Required Element</th>
                                  <th className="p-3 w-1/2">Evidence from Narrative</th>
                                </tr>
                              </thead>
                              <tbody>
                                {res.elements_checked.map((el, idx) => (
                                  <tr key={idx} className="border-b last:border-0 hover:bg-gray-50">
                                    <td className="p-3 text-center">
                                      {el.met ? (
                                        <span className="text-green-600 font-bold text-lg">✓</span>
                                      ) : (
                                        <span className="text-red-500 font-bold text-lg">✗</span>
                                      )}
                                    </td>
                                    <td className="p-3 font-medium text-gray-800">{el.element}</td>
                                    <td className={`p-3 ${!el.met ? 'text-red-600 italic font-medium' : 'text-gray-600'}`}>
                                      {el.evidence}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
