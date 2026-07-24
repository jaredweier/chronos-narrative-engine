"use client";

import { useState, useRef } from "react";

interface EntityMatch {
  label: string;
  matches: string[];
}

export default function DocumentRedactorPage() {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState<string>("");
  const [redactedText, setRedactedText] = useState<string>("");
  const [entities, setEntities] = useState<Record<string, EntityMatch>>({});
  const [activeCategories, setActiveCategories] = useState<string[]>([]);
  const [customTerms, setCustomTerms] = useState<string[]>([]);
  const [newTerm, setNewTerm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      setLoading(true);
      setError("");
      setRedactedText("");

      const formData = new FormData();
      formData.append("file", selectedFile);

      const token = localStorage.getItem("chronos_token") || "";
      
      try {
        const res = await fetch("http://localhost:8765/api/v1/redact/analyze", {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${token}`
          },
          body: formData
        });

        if (!res.ok) throw new Error("Failed to analyze document");
        
        const data = await res.json();
        setText(data.text);
        setEntities(data.entities);
        // Default select all categories that have matches
        setActiveCategories(Object.keys(data.entities));
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
  };

  const addCustomTerm = () => {
    if (newTerm.trim() && !customTerms.includes(newTerm.trim())) {
      setCustomTerms([...customTerms, newTerm.trim()]);
      setNewTerm("");
    }
  };

  const removeCustomTerm = (term: string) => {
    setCustomTerms(customTerms.filter(t => t !== term));
  };

  const toggleCategory = (catId: string) => {
    if (activeCategories.includes(catId)) {
      setActiveCategories(activeCategories.filter(id => id !== catId));
    } else {
      setActiveCategories([...activeCategories, catId]);
    }
  };

  const applyRedactions = async () => {
    setLoading(true);
    setError("");
    const token = localStorage.getItem("chronos_token") || "";

    try {
      const res = await fetch("http://localhost:8765/api/v1/redact/apply", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          text: text,
          categories: activeCategories,
          custom_terms: customTerms
        })
      });

      if (!res.ok) throw new Error("Failed to apply redactions");
      
      const data = await res.json();
      setRedactedText(data.redacted_text);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const exportRedacted = () => {
    const blob = new Blob([redactedText], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "redacted_document.txt";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto min-h-screen flex flex-col font-sans">
      <h1 className="text-3xl font-bold mb-2">Smart Text Redactor</h1>
      <p className="text-gray-600 mb-6">Upload a narrative report (PDF, DOCX, TXT) to automatically identify and redact PII.</p>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      <div className="flex flex-col md:flex-row gap-6 flex-1 min-h-0">
        {/* Sidebar Controls */}
        <div className="w-full md:w-1/3 flex flex-col gap-4">
          <div className="bg-white p-4 border rounded shadow-sm">
            <h2 className="font-semibold text-lg mb-2">1. Upload Document</h2>
            <input 
              type="file" 
              accept=".txt,.pdf,.docx"
              ref={fileInputRef}
              onChange={handleFileUpload}
              className="hidden"
            />
            <button 
              onClick={() => fileInputRef.current?.click()}
              className="bg-gray-800 text-white px-4 py-2 rounded w-full hover:bg-gray-700 transition"
              disabled={loading}
            >
              {loading && !text ? "Analyzing..." : "Choose File (PDF, DOCX, TXT)"}
            </button>
            {file && <p className="text-sm mt-2 text-gray-500 truncate">{file.name}</p>}
          </div>

          <div className="bg-white p-4 border rounded shadow-sm flex-1 overflow-y-auto max-h-96">
            <h2 className="font-semibold text-lg mb-2">2. Auto-Detected Entities</h2>
            {Object.keys(entities).length === 0 ? (
              <p className="text-sm text-gray-500 italic">No entities detected yet.</p>
            ) : (
              <div className="space-y-4">
                {Object.entries(entities).map(([catId, data]) => (
                  <div key={catId} className="border-b pb-2">
                    <label className="flex items-center gap-2 font-medium text-sm mb-1 cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={activeCategories.includes(catId)}
                        onChange={() => toggleCategory(catId)}
                        className="rounded"
                      />
                      {data.label} ({data.matches.length})
                    </label>
                    <div className="flex flex-wrap gap-1 ml-6">
                      {data.matches.map((match, idx) => (
                        <span key={idx} className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">
                          {match}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-white p-4 border rounded shadow-sm">
            <h2 className="font-semibold text-lg mb-2">3. Manual Redactions</h2>
            <div className="flex gap-2 mb-3">
              <input 
                type="text"
                value={newTerm}
                onChange={e => setNewTerm(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addCustomTerm()}
                placeholder="Custom word to redact..."
                className="border p-2 rounded flex-1 text-sm"
              />
              <button 
                onClick={addCustomTerm}
                className="bg-blue-600 text-white px-3 rounded hover:bg-blue-700"
              >
                Add
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {customTerms.map((term, idx) => (
                <span key={idx} className="bg-gray-200 text-gray-800 text-xs px-2 py-1 rounded flex items-center gap-1">
                  {term}
                  <button onClick={() => removeCustomTerm(term)} className="text-red-500 font-bold ml-1 hover:text-red-700">&times;</button>
                </span>
              ))}
            </div>
          </div>

          <div className="bg-white p-4 border rounded shadow-sm">
            <button 
              onClick={applyRedactions}
              disabled={loading || !text}
              className="bg-green-600 text-white font-semibold px-4 py-3 rounded w-full hover:bg-green-700 transition disabled:opacity-50"
            >
              {loading && text && !redactedText ? "Applying..." : "4. Apply Redactions"}
            </button>
          </div>
        </div>

        {/* Main Document View */}
        <div className="w-full md:w-2/3 flex flex-col gap-4">
          <div className="bg-white border rounded shadow-sm flex-1 flex flex-col">
            <div className="bg-gray-50 border-b p-3 font-semibold flex justify-between items-center">
              <span>{redactedText ? "Redacted Result" : "Original Text"}</span>
              {redactedText && (
                <button 
                  onClick={exportRedacted}
                  className="bg-blue-600 text-white px-3 py-1 text-sm rounded hover:bg-blue-700"
                >
                  Export TXT
                </button>
              )}
            </div>
            <div className="p-4 flex-1 overflow-y-auto font-mono text-sm whitespace-pre-wrap leading-relaxed h-[600px]">
              {redactedText ? redactedText : text ? text : (
                <div className="text-gray-400 h-full flex items-center justify-center italic">
                  Upload a document to view text
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
