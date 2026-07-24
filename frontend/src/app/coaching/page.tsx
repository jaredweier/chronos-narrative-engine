"use client";

import { useState } from "react";

interface PerformanceInsights {
  tone_assessment: string;
  tone_notes: string;
  de_escalation_used: boolean;
  de_escalation_notes: string;
  policy_triggers: string[];
  coaching_summary: string;
  error?: string;
}

export default function CoachingDashboard() {
  const [transcript, setTranscript] = useState("");
  const [loading, setLoading] = useState(false);
  const [insights, setInsights] = useState<PerformanceInsights | null>(null);
  const [error, setError] = useState("");

  const handleAnalyze = async () => {
    if (!transcript.trim()) {
      setError("Please paste a transcript to analyze.");
      return;
    }

    setLoading(true);
    setError("");
    setInsights(null);

    try {
      const token = localStorage.getItem("chronos_token") || "";
      const res = await fetch("http://localhost:8765/api/v1/analytics/performance", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ transcript })
      });

      const data = await res.json();
      if (!res.ok || data.status === "error") {
        throw new Error(data.message || "Failed to analyze performance");
      }

      setInsights(data.insights);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getToneColor = (tone: string) => {
    if (tone.toLowerCase() === "professional") return "bg-green-100 text-green-800 border-green-300";
    if (tone.toLowerCase() === "neutral") return "bg-gray-100 text-gray-800 border-gray-300";
    return "bg-red-100 text-red-800 border-red-300";
  };

  return (
    <div className="p-6 max-w-7xl mx-auto min-h-screen flex flex-col font-sans">
      <h1 className="text-3xl font-bold mb-2">Officer Coaching & Performance</h1>
      <p className="text-gray-600 mb-6">Internal tool for communication, tone, and de-escalation coaching.</p>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4 font-medium">
          {error}
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Input */}
        <div className="w-full lg:w-1/2 flex flex-col gap-4">
          <div className="bg-white p-4 border rounded shadow-sm">
            <h2 className="font-semibold text-lg mb-2">Body-Worn Camera Transcript</h2>
            <p className="text-sm text-gray-500 mb-4">Paste the audio transcript below for NLP analysis.</p>
            <textarea
              className="w-full h-[400px] p-3 border rounded font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="[00:00:15] Officer: Sir, please step back..."
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
            />
            <button
              onClick={handleAnalyze}
              disabled={loading}
              className="mt-4 w-full bg-indigo-600 text-white font-bold py-3 rounded shadow hover:bg-indigo-700 disabled:opacity-50 transition"
            >
              {loading ? "Analyzing Interaction..." : "Analyze Performance"}
            </button>
          </div>
        </div>

        {/* Output */}
        <div className="w-full lg:w-1/2 flex flex-col gap-4">
          <div className="bg-white border rounded shadow-sm flex-1 p-6">
            {!insights && !loading && (
              <div className="h-full flex items-center justify-center text-gray-400 italic text-center">
                AI coaching insights will appear here.
              </div>
            )}
            
            {loading && (
              <div className="h-full flex flex-col items-center justify-center text-indigo-600">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mb-4"></div>
                <p className="font-medium animate-pulse">Running NLP sentiment and policy analysis...</p>
              </div>
            )}

            {insights && (
              <div className="space-y-6">
                <div className="flex gap-4 items-stretch">
                  <div className={`flex-1 p-4 rounded border-2 text-center flex flex-col justify-center ${getToneColor(insights.tone_assessment)}`}>
                    <span className="text-xs uppercase font-bold opacity-75 mb-1">Overall Tone</span>
                    <span className="text-2xl font-black">{insights.tone_assessment}</span>
                  </div>
                  <div className={`flex-1 p-4 rounded border-2 text-center flex flex-col justify-center ${insights.de_escalation_used ? 'bg-green-100 border-green-300 text-green-800' : 'bg-gray-100 border-gray-300 text-gray-800'}`}>
                    <span className="text-xs uppercase font-bold opacity-75 mb-1">De-escalation Used</span>
                    <span className="text-2xl font-black">{insights.de_escalation_used ? "YES" : "NO"}</span>
                  </div>
                </div>

                <div>
                  <h3 className="font-bold text-gray-800 border-b pb-1 mb-2">Tone Notes</h3>
                  <p className="text-gray-700 text-sm bg-gray-50 p-3 rounded">{insights.tone_notes}</p>
                </div>

                <div>
                  <h3 className="font-bold text-gray-800 border-b pb-1 mb-2">De-escalation Notes</h3>
                  <p className="text-gray-700 text-sm bg-gray-50 p-3 rounded">{insights.de_escalation_notes}</p>
                </div>

                <div className="bg-yellow-50 border border-yellow-200 rounded p-4">
                  <h3 className="font-bold text-yellow-800 mb-2">Policy & Keyword Triggers</h3>
                  {insights.policy_triggers.length > 0 ? (
                    <ul className="list-disc pl-5 space-y-1 text-sm text-yellow-900 font-medium">
                      {insights.policy_triggers.map((trigger, idx) => (
                        <li key={idx}>{trigger}</li>
                      ))}
                    </ul>
                  ) : (
                    <span className="text-sm text-gray-500 italic">No triggers detected.</span>
                  )}
                </div>

                <div className="bg-blue-50 border border-blue-200 rounded p-4">
                  <h3 className="font-bold text-blue-800 mb-2">Constructive Coaching Summary</h3>
                  <p className="text-blue-900 text-sm leading-relaxed">{insights.coaching_summary}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
