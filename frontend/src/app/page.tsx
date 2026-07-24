"use client";

import React, { useState, useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { jwtDecode } from 'jwt-decode';

export default function Dashboard() {
  const store = useAppStore();
  const [showLogin, setShowLogin] = useState(false);
  const [username, setUsername] = useState('');
  const [badgeId, setBadgeId] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  
  // CAD & Voice Match State
  const [cadInputId, setCadInputId] = useState('');
  const [manualName, setManualName] = useState('');
  const [manualRole, setManualRole] = useState('');
  const [voiceMatchRequired, setVoiceMatchRequired] = useState(false);
  const [uniqueSpeakers, setUniqueSpeakers] = useState<{id: string, startStr: string, startSecs: number}[]>([]);

  // Auto-show login if no token
  useEffect(() => {
    if (!store.token) {
      setShowLogin(true);
    }
  }, [store.token]);

  // Polling for Transcription Task
  useEffect(() => {
    if (!store.transcriptionTaskId) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/v1/tasks/${store.transcriptionTaskId}`, {
          headers: { 'Authorization': `Bearer ${store.token}` }
        });
        if (res.ok) {
          const data = await res.json();
          store.setTranscriptionStatus(data.status);
          
          if (data.status === 'SUCCESS' && data.result) {
            let finalTranscript = data.result;
            
            // Extract unique speakers for voice matching
            const speakerRegex = /\[(\d{2}):(\d{2}(?:\.\d{2})?) -> .*?\] <(SPEAKER_\d+)>/g;
            const speakersMap = new Map<string, {startStr: string, startSecs: number}>();
            let match;
            while ((match = speakerRegex.exec(finalTranscript)) !== null) {
              const [_, mins, secs, speakerId] = match;
              if (!speakersMap.has(speakerId)) {
                speakersMap.set(speakerId, {
                  startStr: `${mins}:${secs}`,
                  startSecs: parseInt(mins) * 60 + parseFloat(secs)
                });
              }
            }

            if (speakersMap.size > 0 && confirm("Do you want to attempt to match voices to individuals?")) {
              setUniqueSpeakers(Array.from(speakersMap.entries()).map(([id, data]) => ({id, ...data})));
              setVoiceMatchRequired(true);
              store.setTranscript(finalTranscript);
            } else {
              // Map SPEAKER_00 to officer name by default if voice match skipped
              if (store.officerName) {
                finalTranscript = finalTranscript.replace(/<SPEAKER_00>/g, `<${store.officerName}>`);
                finalTranscript = finalTranscript.replace(/SPEAKER_00/g, store.officerName);
              }
              store.setTranscript(finalTranscript);
            }
            
            store.setTranscriptionTaskId(null);
            clearInterval(interval);
          } else if (data.status === 'FAILURE') {
            store.setTranscriptionTaskId(null);
            clearInterval(interval);
            console.error('Transcription failed');
          }
        }
      } catch (err) {
        console.error('Polling error', err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [store.transcriptionTaskId, store.token, store.officerName]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !store.token) return;

    const formData = new FormData();
    formData.append("file", file);
    if (store.incidentId) {
      formData.append("incident_id", store.incidentId);
    }

    try {
      const res = await fetch("http://localhost:8000/api/v1/dictation/upload", {
        method: "POST",
        headers: { "Authorization": `Bearer ${store.token}` },
        body: formData
      });
      if (!res.ok) throw new Error("Upload failed");
      const data = await res.json();
      store.setTranscriptionTaskId(data.task_id);
      store.setTranscriptionStatus('PENDING');
      store.setAudioUrl(URL.createObjectURL(file));
    } catch (err) {
      console.error(err);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError('');
    try {
      const res = await fetch('http://localhost:8000/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: username, badge_id: badgeId, password })
      });
      if (!res.ok) throw new Error('Invalid credentials');
      const data = await res.json();
      
      const decoded: any = jwtDecode(data.token);
      store.setToken(data.token, data.role, decoded.name);
      setShowLogin(false);
    } catch (err: any) {
      setLoginError(err.message);
    }
  };

  const handleGenerate = () => {
    if (!store.token) {
      setShowLogin(true);
      return;
    }
    
    store.clearNarrative();
    store.setIsStreaming(true);

    fetch('http://localhost:8000/api/v1/narrative/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${store.token}`
      },
      body: JSON.stringify({
        cad_text: store.cadText || "Mock CAD Data",
        transcript: store.transcript || "Mock Transcript",
        report_type: "Incident Report"
      })
    }).then(async (response) => {
      if (!response.body) return;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      
      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        const chunkValue = decoder.decode(value, { stream: true });
        
        // Very basic SSE parsing
        const lines = chunkValue.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.replace('data: ', '').trim();
            if (dataStr === '[DONE]') {
              store.setIsStreaming(false);
              break;
            }
            try {
              const parsed = JSON.parse(dataStr);
              if (parsed.token) {
                store.appendNarrativeChunk(parsed.token);
              }
            } catch (e) {
               // ignore parse errors for partial chunks
            }
          }
        }
      }
      store.setIsStreaming(false);
    }).catch(err => {
      console.error(err);
      store.setIsStreaming(false);
    });
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 font-sans selection:bg-blue-500/30 relative">
      {/* Login Modal overlay */}
      {showLogin && (
        <div className="absolute inset-0 z-[100] bg-slate-950/80 backdrop-blur-sm flex items-center justify-center">
          <div className="bg-slate-900 border border-slate-700 p-8 rounded-xl w-96 shadow-2xl">
            <h2 className="text-xl font-bold mb-4 text-white">Officer Authentication</h2>
            {loginError && <div className="text-red-400 text-sm mb-4">{loginError}</div>}
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">Name</label>
                <input required type="text" className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white" value={username} onChange={e => setUsername(e.target.value)} />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Badge ID</label>
                <input required type="text" className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white" value={badgeId} onChange={e => setBadgeId(e.target.value)} />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">Password</label>
                <input required type="password" className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white" value={password} onChange={e => setPassword(e.target.value)} />
              </div>
              <button type="submit" className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-2 rounded transition-colors mt-4">
                Login
              </button>
            </form>
          </div>
        </div>
      )}

      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md sticky top-0 z-50">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center font-serif text-xl font-bold">
              &#9878;
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white">Chronos Narrative Engine</h1>
              <p className="text-[10px] uppercase tracking-widest text-slate-400">CJIS Compliant</p>
            </div>
          </div>
          <nav className="flex gap-6 text-sm font-medium text-slate-300">
            <a href="#" className="hover:text-white transition-colors">Dashboard</a>
            <a href="#" className="text-blue-400 hover:text-blue-300 transition-colors">Generate Report</a>
            <a href="/mobile" className="hover:text-white transition-colors">Cruiser Dictation</a>
          </nav>
          <div className="flex items-center gap-4 text-sm text-slate-300">
            {store.officerName ? (
              <div className="flex items-center gap-3">
                <span>{store.officerName} ({store.officerRole})</span>
                <button onClick={() => store.clearToken()} className="text-red-400 hover:text-red-300 text-xs">Logout</button>
              </div>
            ) : (
              <button onClick={() => setShowLogin(true)} className="text-blue-400 hover:text-blue-300">Login</button>
            )}
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-12 gap-8">
          
          <div className="col-span-4 space-y-6">
            {/* Step 1: CAD & Entity UI */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 backdrop-blur-sm">
              <h2 className="text-lg font-semibold mb-4 text-white">1. Incident Info</h2>
              <div className="flex gap-2 mb-4">
                <input 
                  type="text" 
                  placeholder="CAD Incident ID" 
                  className="flex-1 bg-slate-950 border border-slate-700 rounded-md p-2 text-sm text-slate-300"
                  value={cadInputId}
                  onChange={e => setCadInputId(e.target.value)}
                />
                <button onClick={fetchCadData} className="px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-md text-sm text-white">Fetch</button>
              </div>
              
              {store.involvedParties.length > 0 && (
                <div className="mb-4 space-y-2">
                  <h3 className="text-sm text-slate-400 font-medium">Involved Parties</h3>
                  {store.involvedParties.map(p => (
                    <label key={p.id} className="flex items-center gap-2 text-sm text-slate-300 bg-slate-950 p-2 rounded border border-slate-800 cursor-pointer">
                      <input type="checkbox" checked={p.selected} onChange={() => toggleParty(p.id)} className="accent-blue-500" />
                      <span>{p.name} <span className="text-slate-500 text-xs">({p.role})</span></span>
                    </label>
                  ))}
                </div>
              )}
              
              <form onSubmit={addManualParty} className="flex flex-col gap-2 p-3 bg-slate-950 rounded border border-slate-800 mt-4">
                <span className="text-xs text-slate-500">Manual Entry</span>
                <input type="text" placeholder="Name" required className="bg-slate-900 border border-slate-700 rounded p-1 text-sm text-white" value={manualName} onChange={e => setManualName(e.target.value)} />
                <input type="text" placeholder="Role (e.g. Witness)" className="bg-slate-900 border border-slate-700 rounded p-1 text-sm text-white" value={manualRole} onChange={e => setManualRole(e.target.value)} />
                <button type="submit" className="text-xs bg-slate-800 text-slate-300 py-1 rounded hover:bg-slate-700">Add Person</button>
              </form>
            </div>

            {/* Step 2: Evidence Upload */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 backdrop-blur-sm">
              <h2 className="text-lg font-semibold mb-4 text-white">Evidence Upload</h2>
              <label className="border-2 border-dashed border-slate-700 rounded-lg p-8 text-center hover:border-blue-500 hover:bg-slate-800/50 transition-all cursor-pointer block">
                <input type="file" className="hidden" accept="audio/*,video/*" onChange={handleFileUpload} />
                <p className="text-sm text-slate-400">Click or Drag & drop Bodycam Video here</p>
              </label>
              {store.transcriptionStatus && (
                <div className="mt-4 text-sm text-blue-400">
                  Status: {store.transcriptionStatus}
                </div>
              )}
            </div>

            {/* Step 3: Voice Mapping or Transcript Review */}
            {voiceMatchRequired ? (
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 backdrop-blur-sm flex flex-col h-[400px]">
                <h2 className="text-lg font-semibold mb-4 text-white">Voice Matching</h2>
                <p className="text-sm text-slate-400 mb-4">Map detected voices to involved individuals.</p>
                <div className="flex-1 overflow-y-auto space-y-4 pr-2">
                  {uniqueSpeakers.map((speaker, idx) => (
                    <div key={speaker.id} className="bg-slate-950 p-4 rounded-lg border border-slate-800">
                      <div className="flex justify-between items-center mb-2">
                        <span className="font-medium text-blue-400">Voice {idx + 1} ({speaker.id})</span>
                        <span className="text-xs text-slate-500">First speaks at {speaker.startStr}</span>
                      </div>
                      {store.audioUrl && (
                        <audio controls className="w-full h-8 mb-3" src={`${store.audioUrl}#t=${speaker.startSecs}`}></audio>
                      )}
                      <select 
                        className="w-full bg-slate-900 border border-slate-700 text-sm text-slate-200 rounded p-2"
                        value={store.speakerMap[speaker.id] || ""}
                        onChange={(e) => store.updateSpeakerMap(speaker.id, e.target.value)}
                      >
                        <option value="">Select Identity...</option>
                        <option value="Unknown">Unknown Individual</option>
                        {store.officerName && <option value={store.officerName}>{store.officerName} (Officer)</option>}
                        {store.involvedParties.filter(p => p.selected).map(p => (
                          <option key={p.id} value={p.name}>{p.name} ({p.role})</option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
                <div className="mt-4 flex justify-end">
                  <button onClick={applyVoiceMappings} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm text-white font-medium">Apply & Review Transcript</button>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 backdrop-blur-sm flex flex-col h-[400px]">
                <h2 className="text-lg font-semibold mb-4 text-white">Transcript Review</h2>
                <textarea 
                  className="flex-1 bg-slate-950 border border-slate-700 rounded-md p-3 text-sm text-slate-300 font-mono resize-none focus:outline-none focus:border-blue-500"
                  value={store.transcript}
                  onChange={(e) => store.setTranscript(e.target.value)}
                  placeholder="Transcript will appear here for review..."
                />
                <div className="text-xs text-slate-500 mt-2 flex justify-between">
                  <span>Check words marked with [?]</span>
                  {store.transcript.includes('[?]') && <span className="text-amber-500 font-bold">Low Confidence Detected</span>}
                </div>
                {store.audioUrl && (
                  <div className="mt-4">
                    <audio controls className="w-full h-10" src={store.audioUrl}></audio>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="col-span-8">
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 h-[600px] flex flex-col backdrop-blur-sm relative overflow-hidden">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-600 to-indigo-600"></div>
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-lg font-semibold text-white">AI Narrative Generation</h2>
                <div className="flex gap-2">
                  <span className="px-2 py-1 rounded text-xs font-medium bg-blue-500/20 text-blue-400 border border-blue-500/30">
                    {store.isStreaming ? 'Streaming...' : 'SSE Ready'}
                  </span>
                </div>
              </div>
              
              <div className="flex-1 rounded-md border border-slate-800 bg-slate-950 p-4 font-mono text-sm text-slate-300 overflow-y-auto whitespace-pre-wrap">
                {store.narrativeStream}
                {store.isStreaming && <span className="animate-pulse inline-block w-2 h-4 bg-blue-500 ml-1"></span>}
              </div>
              
              <div className="mt-6 flex justify-end gap-3">
                <button onClick={() => store.clearNarrative()} className="px-4 py-2 rounded-md text-sm font-medium text-slate-300 hover:text-white transition-colors">
                  Clear
                </button>
                <button disabled={store.isStreaming} onClick={handleGenerate} className="px-4 py-2 rounded-md bg-blue-600 text-sm font-medium text-white hover:bg-blue-500 transition-all shadow-[0_0_15px_rgba(37,99,235,0.3)] disabled:opacity-50">
                  Generate Narrative
                </button>
              </div>
            </div>
          </div>
          
        </div>
      </main>
    </div>
  );
}
