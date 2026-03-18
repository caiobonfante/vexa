"use client";

import { useState, useEffect } from "react";
import { Monitor, Plus, ExternalLink, Trash2, Loader2, Save, Copy, RefreshCw, PanelRightOpen, PanelRightClose, Check, GitBranch } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface BrowserSession {
  id: number;
  status: string;
  data: {
    mode: string;
    session_token: string;
    ssh_port?: number;
  };
  created_at: string;
}

interface GitConfig {
  repo: string;
  token: string;
  branch: string;
}

function loadGitConfig(): GitConfig {
  if (typeof window === "undefined") return { repo: "", token: "", branch: "main" };
  try {
    const stored = localStorage.getItem("vexa-browser-git");
    if (stored) return JSON.parse(stored);
  } catch {}
  return { repo: "", token: "", branch: "main" };
}

function saveGitConfig(config: GitConfig) {
  localStorage.setItem("vexa-browser-git", JSON.stringify(config));
}

function CopyBlock({ label, text }: { label: string; text: string }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
        <button
          className="text-xs text-primary hover:underline"
          onClick={() => { navigator.clipboard.writeText(text); toast.success(`${label} copied`); }}
        >
          Copy
        </button>
      </div>
      <pre
        className="p-2 bg-muted rounded text-xs font-mono whitespace-pre-wrap break-all cursor-pointer hover:bg-muted/80"
        onClick={() => { navigator.clipboard.writeText(text); toast.success(`${label} copied`); }}
      >{text}</pre>
    </div>
  );
}

export default function BrowserPage() {
  const [session, setSession] = useState<BrowserSession | null>(null);
  const [apiUrl, setApiUrl] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [showPanel, setShowPanel] = useState(false);
  const [gitConfig, setGitConfig] = useState<GitConfig>({ repo: "", token: "", branch: "main" });
  const [isSyncing, setIsSyncing] = useState(false);
  const [gitSaved, setGitSaved] = useState(false);

  useEffect(() => {
    setGitConfig(loadGitConfig());
    setGitSaved(!!loadGitConfig().repo);
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
      const body: Record<string, string> = { mode: "browser_session" };
      const git = loadGitConfig();
      if (git.repo && git.token) {
        body.workspaceGitRepo = git.repo;
        body.workspaceGitToken = git.token;
        body.workspaceGitBranch = git.branch || "main";
      }
      const response = await fetch("/api/vexa/bots", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(await response.text());
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

  function handleSaveGitConfig() {
    saveGitConfig(gitConfig);
    setGitSaved(true);
    toast.success("Git workspace saved");
  }

  async function handleSyncGitConfig() {
    // Save first
    saveGitConfig(gitConfig);
    setGitSaved(true);
    setIsSyncing(true);
    try {
      // Test connection by checking if repo is accessible
      // We verify by trying to access the GitHub API
      const repoPath = gitConfig.repo
        .replace('https://github.com/', '')
        .replace('.git', '');
      const response = await fetch(`https://api.github.com/repos/${repoPath}`, {
        headers: gitConfig.token ? { Authorization: `Bearer ${gitConfig.token}` } : {},
      });
      if (response.ok) {
        toast.success("Connected — repo accessible");
      } else if (response.status === 404) {
        toast.error("Repo not found — check URL and token permissions");
      } else {
        toast.error(`GitHub API error: ${response.status}`);
      }
    } catch (error) {
      toast.error("Connection failed: " + (error as Error).message);
    } finally {
      setIsSyncing(false);
    }
  }

  const token = session?.data?.session_token;
  const vncUrl = token && apiUrl ? `${apiUrl}/b/${token}/vnc/vnc.html?autoconnect=true&resize=scale&reconnect=true&path=b/${token}/vnc/websockify` : null;
  const cdpUrl = token && apiUrl ? `${apiUrl}/b/${token}/cdp` : null;
  const mcpUrl = apiUrl ? `${apiUrl}/mcp` : null;

  const sshPort = session?.data?.ssh_port;
  const sshHost = apiUrl ? new URL(apiUrl).hostname : "localhost";

  const agentInstructions = cdpUrl ? [
    `You have access to a remote browser session. The user can see everything you do live via VNC.`,
    ``,
    `Browser control (Playwright CDP):`,
    `  const browser = await chromium.connectOverCDP('${cdpUrl}');`,
    `  const page = browser.contexts()[0].pages()[0];`,
    `  // goto, click, fill, screenshot, evaluate, waitForSelector, etc.`,
    ``,
    ...(sshPort ? [
      `Shell access (SSH into the container):`,
      `  ssh root@${sshHost} -p ${sshPort}`,
      `  Password: vexa`,
      `  Workspace: /workspace`,
      ``,
    ] : []),
    `The browser is a full Chromium instance. The user sees your actions in real time.`,
  ].join('\n') : "";

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-64px)]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!session) {
    const hasGit = gitConfig.repo && gitConfig.token;
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-64px)] gap-6">
        <div className="flex flex-col items-center gap-2">
          <Monitor className="h-16 w-16 text-muted-foreground" />
          <h2 className="text-xl font-semibold">Remote Browser</h2>
          <p className="text-muted-foreground text-center max-w-md">
            Interactive browser with persistent storage. Authenticate
            accounts, run scripts, control via Playwright CDP.
          </p>
        </div>

        <Button size="lg" onClick={createSession} disabled={isCreating}>
          {isCreating ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <Plus className="h-4 w-4 mr-2" />
          )}
          {isCreating ? "Starting..." : "Start Browser Session"}
        </Button>

        {/* Git workspace — always visible, user-level setting */}
        <div className="w-full max-w-md space-y-3 p-4 border rounded-lg bg-card">
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-muted-foreground" />
            <h3 className="font-medium text-sm">Git Workspace</h3>
            {gitSaved && hasGit && <Check className="h-3 w-3 text-green-500" />}
          </div>
          <p className="text-xs text-muted-foreground">
            Sync workspace files with a GitHub repo. Use a fine-grained PAT scoped to this repo only.
          </p>
          <input
            className="w-full px-3 py-2 text-sm border rounded bg-background"
            placeholder="https://github.com/you/bot-workspace.git"
            value={gitConfig.repo}
            onChange={e => { setGitConfig({ ...gitConfig, repo: e.target.value }); setGitSaved(false); }}
          />
          <input
            className="w-full px-3 py-2 text-sm border rounded bg-background"
            placeholder="github_pat_..."
            type="password"
            value={gitConfig.token}
            onChange={e => { setGitConfig({ ...gitConfig, token: e.target.value }); setGitSaved(false); }}
          />
          <input
            className="w-full px-3 py-2 text-sm border rounded bg-background"
            placeholder="Branch (default: main)"
            value={gitConfig.branch}
            onChange={e => { setGitConfig({ ...gitConfig, branch: e.target.value }); setGitSaved(false); }}
          />
          <div className="flex gap-2">
            <Button size="sm" onClick={handleSaveGitConfig} disabled={!gitConfig.repo}>
              Save
            </Button>
            <Button size="sm" variant="outline" onClick={handleSyncGitConfig} disabled={!gitConfig.repo || !gitConfig.token || isSyncing}>
              {isSyncing ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <RefreshCw className="h-3 w-3 mr-1" />}
              Test Connection
            </Button>
          </div>
        </div>
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
        <Button variant={showPanel ? "default" : "outline"} size="sm" onClick={() => setShowPanel(!showPanel)}>
          {showPanel ? <PanelRightClose className="h-4 w-4 mr-1" /> : <PanelRightOpen className="h-4 w-4 mr-1" />}
          Connect Agent
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

      {/* Content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Browser iframe */}
        <div className="flex-1 min-w-0">
          {vncUrl ? (
            <iframe
              src={vncUrl}
              className="w-full h-full border-0"
              allow="clipboard-read; clipboard-write"
            />
          ) : (
            <div className="h-full flex items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          )}
        </div>

        {/* Connect Agent sidebar */}
        {showPanel && (
          <div className="w-96 border-l bg-card p-4 flex flex-col gap-4 overflow-y-auto">
            <div>
              <h3 className="font-semibold text-sm mb-1">Connect Agent</h3>
              <p className="text-xs text-muted-foreground">
                Copy the instructions below into Claude or any AI agent to give it control of this browser.
              </p>
            </div>

            <CopyBlock label="Agent Instructions" text={agentInstructions} />

            <hr />

            <CopyBlock label="CDP URL" text={cdpUrl || ""} />

            {sshPort && (
              <>
                <hr />
                <CopyBlock label="SSH" text={`ssh root@${sshHost} -p ${sshPort}\nPassword: vexa`} />
              </>
            )}

            <hr />

            <div className="space-y-2">
              <h4 className="text-xs font-medium">MCP Server</h4>
              <p className="text-xs text-muted-foreground">
                Connect Claude Desktop or any MCP client.
              </p>
              <CopyBlock label="MCP Endpoint" text={mcpUrl || ""} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
