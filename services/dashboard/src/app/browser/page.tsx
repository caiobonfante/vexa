"use client";

import { useState, useEffect } from "react";
import { Monitor, Plus, ExternalLink, Trash2, Loader2, Save, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface BrowserSession {
  id: number;
  status: string;
  data: {
    mode: string;
    session_token: string;
  };
  created_at: string;
}

export default function BrowserPage() {
  const [session, setSession] = useState<BrowserSession | null>(null);
  const [apiUrl, setApiUrl] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetch("/api/config").then(r => r.json()).then(cfg => {
      setApiUrl(cfg.publicApiUrl || cfg.apiUrl || "http://localhost:8056");
      fetchActiveSession();
    });
  }, []);

  async function fetchActiveSession() {
    setIsLoading(true);
    try {
      const response = await fetch("/api/vexa/meetings");
      if (response.ok) {
        const data = await response.json();
        const meetings = data.meetings || [];
        const sessions = meetings
          .filter((m: BrowserSession) => m.data?.mode === "browser_session" && m.status === "active");
        setSession(sessions[0] || null);
      }
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    } finally {
      setIsLoading(false);
      setIsCreating(false);
    }
  }

  async function createSession() {
    setIsCreating(true);
    try {
      const response = await fetch("/api/vexa/bots", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "browser_session" }),
      });
      if (!response.ok) throw new Error(await response.text());
      // After creating, wait a moment for container to start, then fetch active sessions
      setTimeout(() => fetchActiveSession(), 3000);
      toast.success("Browser session created — starting container...");
    } catch (error) {
      toast.error("Failed to create session: " + (error as Error).message);
      setIsCreating(false);
    }
  }

  async function saveStorage() {
    if (!session) return;
    setIsSaving(true);
    try {
      const token = session.data.session_token;
      const response = await fetch(`${apiUrl}/b/${token}/save`, { method: "POST" });
      if (!response.ok) throw new Error(await response.text());
      toast.success("Storage saved");
    } catch (error) {
      toast.error("Save failed: " + (error as Error).message);
    } finally {
      setIsSaving(false);
    }
  }

  async function stopSession() {
    if (!session) return;
    try {
      await fetch(`/api/vexa/bots/browser_session/${session.id}`, { method: "DELETE" });
      setSession(null);
      toast.success("Session stopped");
    } catch (error) {
      toast.error("Failed to stop session");
    }
  }

  const token = session?.data?.session_token;
  const vncUrl = token && apiUrl ? `${apiUrl}/b/${token}/vnc/vnc.html?autoconnect=true&resize=scale&reconnect=true&path=b/${token}/vnc/websockify` : null;
  const cdpUrl = token && apiUrl ? `${apiUrl}/b/${token}/cdp` : null;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-64px)]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-64px)] gap-4">
        <Monitor className="h-16 w-16 text-muted-foreground" />
        <h2 className="text-xl font-semibold">Remote Browser</h2>
        <p className="text-muted-foreground text-center max-w-md">
          Interactive browser with persistent storage. Authenticate accounts,
          run scripts, control via Playwright CDP.
        </p>
        <Button size="lg" onClick={createSession} disabled={isCreating}>
          {isCreating ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <Plus className="h-4 w-4 mr-2" />
          )}
          {isCreating ? "Starting..." : "Start Browser Session"}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-64px)]">
      {/* Toolbar */}
      <div className="flex items-center gap-2 p-2 border-b bg-background">
        <Monitor className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">Session #{session.id}</span>
        <div className="flex-1" />
        <Button variant="outline" size="sm" onClick={saveStorage} disabled={isSaving}>
          {isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Save className="h-4 w-4 mr-1" />}
          Save
        </Button>
        <Button variant="outline" size="sm" onClick={() => {
          if (cdpUrl) { navigator.clipboard.writeText(cdpUrl); toast.success("CDP URL copied"); }
        }}>
          <Copy className="h-4 w-4 mr-1" />
          CDP
        </Button>
        <Button variant="outline" size="sm" onClick={() => { if (vncUrl) window.open(vncUrl, "_blank"); }}>
          <ExternalLink className="h-4 w-4 mr-1" />
          Fullscreen
        </Button>
        <Button variant="destructive" size="sm" onClick={stopSession}>
          <Trash2 className="h-4 w-4 mr-1" />
          Stop
        </Button>
      </div>

      {/* Browser iframe */}
      {vncUrl ? (
        <iframe
          src={vncUrl}
          className="flex-1 w-full border-0"
          allow="clipboard-read; clipboard-write"
        />
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}
    </div>
  );
}
