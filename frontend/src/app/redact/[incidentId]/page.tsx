"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useSearchParams } from "next/navigation";

interface Detection {
  type: string;
  box: [number, number, number, number];
  score: number;
}

interface RedactionData {
  [frame: string]: Detection[];
}

interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export default function InteractiveRedactPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const incidentId = params.incidentId as string;
  const videoFilename = searchParams.get("video") || "evidence.mp4";
  
  const videoRef = useRef<HTMLVideoElement>(null);
  const [detections, setDetections] = useState<RedactionData>({});
  const [transcript, setTranscript] = useState<TranscriptSegment[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [currentTime, setCurrentTime] = useState(0);

  const token = typeof window !== 'undefined' ? localStorage.getItem("chronos_token") : "";
  const videoUrl = `http://localhost:8765/api/v1/evidence/${incidentId}/${videoFilename}?token=${token}`;

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`http://localhost:8765/api/v1/video/${incidentId}/detections?video_filename=${encodeURIComponent(videoFilename)}`, {
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          setDetections(data.detections || {});
        }
        
        // Mocking transcript data for now (ideally this would be another API fetch)
        setTranscript([
          { start: 0, end: 5, text: "Dispatch this is Unit 4, arriving on scene." },
          { start: 5, end: 12, text: "I see the suspect vehicle, a white sedan." },
          { start: 12, end: 15, text: "Suspect is exiting the vehicle." },
          { start: 15, end: 18, text: "Show me your hands! Drop the weapon!" }
        ]);
        
      } catch (e) {
        console.error(e);
        setMessage("Error loading data.");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [incidentId, videoFilename, token]);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const jumpToTime = (time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      videoRef.current.play();
    }
  };

  const currentFrameStr = `frame_${Math.floor(currentTime) + 1 === 0 ? 1 : Math.floor(currentTime) + 1}`.padStart(14, '0').replace('000000000', ''); 
  // format: frame_0001.jpg
  const formattedFrameStr = `frame_${String(Math.floor(currentTime) + 1).padStart(4, '0')}.jpg`;
  
  const currentDetections = detections[formattedFrameStr] || [];

  return (
    <div className="p-4 max-w-7xl mx-auto h-screen flex flex-col">
      <h1 className="text-2xl font-bold mb-4">Interactive Review & Redaction</h1>
      
      <div className="flex gap-6 flex-1 min-h-0">
        {/* Left Side: Video Player */}
        <div className="flex-1 flex flex-col">
          <div className="relative bg-black rounded-lg overflow-hidden flex-1 shadow-lg border border-gray-800">
            <video 
              ref={videoRef}
              src={videoUrl}
              controls
              className="absolute inset-0 w-full h-full object-contain"
              onTimeUpdate={handleTimeUpdate}
            />
            {/* Overlay Bounding Boxes */}
            {currentDetections.map((det, i) => {
              // Basic mapping (assumes video matches rendered dimensions roughly)
              // In a real app, calculate relative % based on native video resolution vs rendered width/height
              const [x1, y1, x2, y2] = det.box;
              const width = x2 - x1;
              const height = y2 - y1;
              return (
                <div 
                  key={i}
                  className="absolute border-2 border-red-500 bg-red-500 bg-opacity-20 flex items-start justify-center text-xs text-white font-bold cursor-pointer hover:bg-opacity-0 transition"
                  style={{
                    left: `${(x1 / 1920) * 100}%`, // Assuming 1080p source for this demo calc
                    top: `${(y1 / 1080) * 100}%`,
                    width: `${(width / 1920) * 100}%`,
                    height: `${(height / 1080) * 100}%`
                  }}
                  onClick={() => alert(`Remove redaction for ${det.type}?`)}
                >
                  <span className="bg-red-500 px-1 mt-1 rounded">{det.type}</span>
                </div>
              );
            })}
          </div>
          
          <div className="mt-4 p-4 bg-gray-100 rounded">
            <h3 className="font-semibold mb-2">Video Controls</h3>
            <p className="text-sm text-gray-600 mb-2">Current Frame: {formattedFrameStr}</p>
            <button className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded text-sm w-full">
              Apply Redactions & Render
            </button>
          </div>
        </div>
        
        {/* Right Side: Interactive Transcript */}
        <div className="w-1/3 bg-white border shadow-sm rounded-lg flex flex-col h-full overflow-hidden">
          <div className="bg-gray-100 p-3 border-b font-semibold">
            Interactive Transcript
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {transcript.map((seg, i) => {
              const isActive = currentTime >= seg.start && currentTime <= seg.end;
              return (
                <div 
                  key={i} 
                  onClick={() => jumpToTime(seg.start)}
                  className={`p-3 rounded border cursor-pointer transition ${isActive ? 'bg-blue-50 border-blue-400' : 'hover:bg-gray-50'}`}
                >
                  <div className="text-xs text-gray-500 mb-1 font-mono">
                    [{seg.start}s - {seg.end}s]
                  </div>
                  <p className={`text-sm ${isActive ? 'font-medium text-gray-900' : 'text-gray-700'}`}>
                    {seg.text}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
        
      </div>
    </div>
  );
}
