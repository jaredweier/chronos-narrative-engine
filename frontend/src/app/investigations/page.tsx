"use client";

import { useState } from "react";

interface CaseBrief {
  key_facts: string[];
  suspects: string[];
  evidence: string[];
  summary_narrative: string;
}

export default function InvestigationsPage() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [brief, setBrief] = useState<CaseBrief | null>(null);
  const [error, setError] = useState("");

  const handleGenerate = async () => {
    if (!text.trim()) {
      setError("Please paste some case file text to analyze.");
      return;
    }

    setLoading(true);
    setError("");
    setBrief(null);

    try {
      const token = localStorage.getItem("chronos_token") || "";
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/case-briefs`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ text })
      });

      const data = await res.json();
      if (!res.ok || data.status === "error") {
        throw new Error(data.message || "Failed to generate case brief");
      }

      setBrief(data.brief);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto min-h-screen flex flex-col font-sans">
      <h1 className="text-3xl font-bold mb-2">Automated Case Briefs</h1>
      <p className="text-gray-600 mb-6">Instantly summarize large case files into actionable intelligence briefs.</p>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4 font-medium">
          {error}
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-6">
        
        {/* Left Side: Input */}
        <div className="w-full lg:w-1/2 flex flex-col gap-4">
          <div className="bg-white p-4 border rounded shadow-sm">
            <h2 className="font-semibold text-lg mb-4 border-b pb-2">Source Material</h2>
            <textarea
              className="w-full h-[500px] p-3 border rounded font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Paste raw text from CAD reports, witness statements, or case files here..."
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <button
              onClick={handleGenerate}
              disabled={loading}
              className="mt-4 w-full bg-blue-600 text-white font-bold py-3 rounded shadow hover:bg-blue-700 disabled:opacity-50 transition"
            >
              {loading ? "Generating Brief (This may take a minute)..." : "Generate Case Brief"}
            </button>
          </div>
        </div>

        {/* Right Side: Output */}
        <div className="w-full lg:w-1/2 flex flex-col gap-4">
          <div className="bg-white border rounded shadow-sm flex-1 p-6">
            {!brief && !loading && (
              <div className="h-full flex items-center justify-center text-gray-400 italic text-center">
                Your AI-generated case brief will appear here.
              </div>
            )}
            
            {loading && (
              <div className="h-full flex flex-col items-center justify-center text-blue-600">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
                <p className="font-medium animate-pulse">Reading case file and extracting facts...</p>
              </div>
            )}

            {brief && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xl font-bold border-b-2 border-gray-800 pb-2 mb-3">Executive Summary</h3>
                  <p className="text-gray-800 leading-relaxed bg-gray-50 p-4 rounded italic">
                    {brief.summary_narrative}
                  </p>
                </div>

                <div>
                  <h3 className="text-lg font-bold text-blue-800 border-b pb-1 mb-2">Key Facts</h3>
                  <ul className="list-disc pl-5 space-y-1">
                    {brief.key_facts.map((fact, idx) => (
                      <li key={idx} className="text-gray-700">{fact}</li>
                    ))}
                  </ul>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-red-50 p-4 rounded border border-red-100">
                    <h3 className="font-bold text-red-800 mb-2">Suspects / Persons of Interest</h3>
                    {brief.suspects.length > 0 ? (
                      <ul className="list-disc pl-5 space-y-1 text-sm text-red-900">
                        {brief.suspects.map((suspect, idx) => (
                          <li key={idx}>{suspect}</li>
                        ))}
                      </ul>
                    ) : (
                      <span className="text-sm text-gray-500">None identified.</span>
                    )}
                  </div>

                  <div className="bg-amber-50 p-4 rounded border border-amber-100">
                    <h3 className="font-bold text-amber-800 mb-2">Evidence</h3>
                    {brief.evidence.length > 0 ? (
                      <ul className="list-disc pl-5 space-y-1 text-sm text-amber-900">
                        {brief.evidence.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    ) : (
                      <span className="text-sm text-gray-500">None documented.</span>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
