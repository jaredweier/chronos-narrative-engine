import { create } from 'zustand';

export interface InvolvedParty {
  id: string;
  name: string;
  role: string;
  selected: boolean;
}

interface AppState {
  token: string | null;
  officerRole: string | null;
  officerName: string | null;
  incidentId: string | null;
  cadText: string;
  transcript: string;
  narrativeStream: string;
  isStreaming: boolean;
  audioUrl: string | null;
  transcriptionTaskId: string | null;
  transcriptionStatus: string | null;
  involvedParties: InvolvedParty[];
  speakerMap: Record<string, string>;
  setToken: (token: string, role: string, name: string) => void;
  clearToken: () => void;
  setIncidentId: (id: string) => void;
  setCadText: (text: string) => void;
  setTranscript: (text: string) => void;
  appendNarrativeChunk: (chunk: string) => void;
  clearNarrative: () => void;
  setIsStreaming: (isStreaming: boolean) => void;
  setAudioUrl: (url: string | null) => void;
  setTranscriptionTaskId: (taskId: string | null) => void;
  setTranscriptionStatus: (status: string | null) => void;
  setInvolvedParties: (parties: InvolvedParty[]) => void;
  updateSpeakerMap: (speakerId: string, name: string) => void;
  clearSpeakerMap: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  token: null,
  officerRole: null,
  officerName: null,
  incidentId: null,
  cadText: '',
  transcript: '',
  narrativeStream: '',
  isStreaming: false,
  audioUrl: null,
  transcriptionTaskId: null,
  transcriptionStatus: null,
  involvedParties: [],
  speakerMap: {},
  
  setToken: (token, role, name) => set({ token, officerRole: role, officerName: name }),
  clearToken: () => set({ token: null, officerRole: null, officerName: null }),
  setIncidentId: (id) => set({ incidentId: id }),
  setCadText: (text) => set({ cadText: text }),
  setTranscript: (text) => set({ transcript: text }),
  appendNarrativeChunk: (chunk) => set((state) => ({ narrativeStream: state.narrativeStream + chunk })),
  clearNarrative: () => set({ narrativeStream: '' }),
  setIsStreaming: (isStreaming) => set({ isStreaming }),
  setAudioUrl: (url) => set({ audioUrl: url }),
  setTranscriptionTaskId: (taskId) => set({ transcriptionTaskId: taskId }),
  setTranscriptionStatus: (status) => set({ transcriptionStatus: status }),
  setInvolvedParties: (parties) => set({ involvedParties: parties }),
  updateSpeakerMap: (speakerId, name) => set((state) => ({ 
    speakerMap: { ...state.speakerMap, [speakerId]: name } 
  })),
  clearSpeakerMap: () => set({ speakerMap: {} }),
}));