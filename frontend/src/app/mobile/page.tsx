"use client";

import React, { useState, useRef } from "react";
import { useAppStore } from "../../store/useAppStore";

export default function MobileDictation() {
  const store = useAppStore();
  const [isRecording, setIsRecording] = useState(false);
  const [statusMsg, setStatusMsg] = useState("Press and hold the button to record");
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const audioChunks = useRef<Blob[]>([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder.current = new MediaRecorder(stream);
      audioChunks.current = [];

      mediaRecorder.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.current.push(event.data);
        }
      };

      mediaRecorder.current.onstop = async () => {
        const audioBlob = new Blob(audioChunks.current, { type: "audio/webm" });
        await uploadAudio(audioBlob);
      };

      mediaRecorder.current.start();
      setIsRecording(true);
      setStatusMsg("Recording...");
    } catch (err) {
      console.error("Microphone access denied", err);
      setStatusMsg("Microphone access denied");
    }
  };

  const stopRecording = () => {
    if (mediaRecorder.current && isRecording) {
      mediaRecorder.current.stop();
      mediaRecorder.current.stream.getTracks().forEach(track => track.stop());
      setIsRecording(false);
      setStatusMsg("Processing dictation...");
    }
  };

  const uploadAudio = async (audioBlob: Blob) => {
    if (!store.token) {
      setStatusMsg("Error: Not logged in");
      return;
    }

    const formData = new FormData();
    formData.append("file", audioBlob, "dictation.webm");
    
    // Send incident_id if available in store
    if (store.incidentId) {
      formData.append("incident_id", store.incidentId);
    }

    try {
      const res = await fetch("http://localhost:8000/api/v1/dictation/upload", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${store.token}`
        },
        body: formData,
      });

      if (!res.ok) throw new Error("Upload failed");
      const data = await res.json();
      
      setStatusMsg(`Success! Task ID: ${data.task_id}`);
    } catch (err: any) {
      console.error(err);
      setStatusMsg(`Upload error: ${err.message}`);
    }
  };

  const handlePointerDown = (e: React.PointerEvent) => {
    e.preventDefault();
    startRecording();
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    e.preventDefault();
    stopRecording();
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 text-gray-900 p-4">
      <div className="absolute top-4 right-4 text-sm font-medium">
        {store.officerName ? `Logged in: ${store.officerName}` : "Not logged in"}
      </div>
      <h1 className="text-3xl font-bold mb-8 text-center text-blue-900">
        Cruiser Dictation
      </h1>
      <div className="flex-grow flex items-center justify-center w-full max-w-sm">
        <button
          onPointerDown={handlePointerDown}
          onPointerUp={handlePointerUp}
          onPointerLeave={handlePointerUp}
          className={`w-48 h-48 rounded-full flex items-center justify-center text-white text-2xl font-bold transition-all shadow-lg select-none ${
            isRecording ? "bg-red-600 scale-95 shadow-inner" : "bg-blue-600 hover:bg-blue-700"
          }`}
          style={{ touchAction: "none" }}
        >
          {isRecording ? "Recording..." : "Hold to Dictate"}
        </button>
      </div>
      <div className="mt-8 text-sm text-gray-500 font-medium">
        {statusMsg}
      </div>
    </div>
  );
}
