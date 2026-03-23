import { create } from "zustand";

export interface AgentMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  tools?: { tool: string; summary: string }[];
  timestamp: number;
}

interface AgentState {
  messages: AgentMessage[];
  isStreaming: boolean;
  userId: string;

  addMessage: (msg: AgentMessage) => void;
  updateLastAssistant: (content: string, tools?: { tool: string; summary: string }[]) => void;
  setStreaming: (v: boolean) => void;
  setUserId: (id: string) => void;
  clearMessages: () => void;
}

export const useAgentStore = create<AgentState>()((set) => ({
  messages: [],
  isStreaming: false,
  userId: "dima",

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  updateLastAssistant: (content, tools) =>
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === "assistant") {
        msgs[msgs.length - 1] = { ...last, content, tools: tools || last.tools };
      }
      return { messages: msgs };
    }),

  setStreaming: (v) => set({ isStreaming: v }),
  setUserId: (id) => set({ userId: id }),
  clearMessages: () => set({ messages: [] }),
}));
