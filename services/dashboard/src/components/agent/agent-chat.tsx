"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Send, Square, RotateCcw, Loader2, Wrench, Bot, User } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAgentStore, AgentMessage } from "@/stores/agent-store";
import { useAuthStore } from "@/stores/auth-store";

const AGENT_API = process.env.NEXT_PUBLIC_AGENT_API_URL || "/api/agent";

function ToolChip({ tool, summary }: { tool: string; summary: string }) {
  return (
    <Badge variant="secondary" className="text-xs gap-1 font-normal">
      <Wrench className="h-3 w-3" />
      {summary || tool}
    </Badge>
  );
}

function MessageBubble({ msg }: { msg: AgentMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
          <Bot className="h-4 w-4 text-primary" />
        </div>
      )}
      <div className={`max-w-[80%] ${isUser ? "order-first" : ""}`}>
        <div
          className={`rounded-lg px-4 py-2 ${
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted"
          }`}
        >
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
          ) : (
            <div className="text-sm prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {msg.content || "..."}
              </ReactMarkdown>
            </div>
          )}
        </div>
        {msg.tools && msg.tools.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {msg.tools.map((t, i) => (
              <ToolChip key={i} tool={t.tool} summary={t.summary} />
            ))}
          </div>
        )}
      </div>
      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center">
          <User className="h-4 w-4 text-primary-foreground" />
        </div>
      )}
    </div>
  );
}

export function AgentChat() {
  const {
    messages,
    isStreaming,
    addMessage,
    updateLastAssistant,
    setStreaming,
    clearMessages,
  } = useAgentStore();

  // Use logged-in user's ID and token
  const { user, token } = useAuthStore();
  const userId = user?.id?.toString() || user?.email || "default";

  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMessage = useCallback(async () => {
    const msg = input.trim();
    if (!msg || isStreaming) return;
    setInput("");

    // Add user message
    addMessage({
      id: `user-${Date.now()}`,
      role: "user",
      content: msg,
      timestamp: Date.now(),
    });

    // Add placeholder assistant message
    addMessage({
      id: `assistant-${Date.now()}`,
      role: "assistant",
      content: "",
      tools: [],
      timestamp: Date.now(),
    });

    setStreaming(true);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const resp = await fetch(`${AGENT_API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, message: msg }),
        signal: controller.signal,
      });

      if (!resp.ok || !resp.body) {
        updateLastAssistant(`Error: ${resp.status} ${resp.statusText}`);
        setStreaming(false);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";
      let tools: { tool: string; summary: string }[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === "text_delta") {
              accumulated += event.text || "";
              updateLastAssistant(accumulated, tools);
            } else if (event.type === "tool_use") {
              tools = [...tools, { tool: event.tool, summary: event.summary }];
              updateLastAssistant(accumulated, tools);
            } else if (event.type === "error") {
              accumulated += `\n\n⚠️ ${event.message}`;
              updateLastAssistant(accumulated, tools);
            }
          } catch {}
        }
      }
    } catch (err: any) {
      if (err.name !== "AbortError") {
        updateLastAssistant(`Error: ${err.message}`);
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }, [input, isStreaming, userId, addMessage, updateLastAssistant, setStreaming]);

  const handleStop = useCallback(async () => {
    abortRef.current?.abort();
    try {
      await fetch(`${AGENT_API}/chat`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId }),
      });
    } catch {}
    setStreaming(false);
  }, [userId, setStreaming]);

  const handleReset = useCallback(async () => {
    await handleStop();
    try {
      await fetch(`${AGENT_API}/chat/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId }),
      });
    } catch {}
    clearMessages();
  }, [userId, handleStop, clearMessages]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-primary" />
          <h2 className="font-semibold">Vexa Agent</h2>
          {isStreaming && (
            <Badge variant="secondary" className="text-xs">
              <Loader2 className="h-3 w-3 animate-spin mr-1" />
              Thinking...
            </Badge>
          )}
        </div>
        <Button variant="ghost" size="sm" onClick={handleReset}>
          <RotateCcw className="h-4 w-4 mr-1" />
          Reset
        </Button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p>Send a message to start chatting with your Vexa agent.</p>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
      </div>

      {/* Input */}
      <div className="border-t p-4">
        <div className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message your agent..."
            disabled={isStreaming}
            className="flex-1"
          />
          {isStreaming ? (
            <Button variant="destructive" onClick={handleStop}>
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button onClick={sendMessage} disabled={!input.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
