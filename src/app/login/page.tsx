"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Mail, Loader2, CheckCircle, ArrowLeft, AlertTriangle, XCircle } from "lucide-react";
import { Logo } from "@/components/ui/logo";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthStore } from "@/stores/auth-store";
import { toast } from "sonner";

type LoginState = "email" | "sent";

interface HealthStatus {
  status: "ok" | "degraded" | "error";
  authMode: "direct" | "magic-link";
  checks: {
    smtp: { configured: boolean; optional?: boolean; error?: string };
    adminApi: { configured: boolean; reachable: boolean; error?: string };
    vexaApi: { configured: boolean; reachable: boolean; error?: string };
  };
  missingConfig: string[];
}

export default function LoginPage() {
  const router = useRouter();
  const { sendMagicLink, isLoading, isAuthenticated } = useAuthStore();
  const [email, setEmail] = useState("");
  const [state, setState] = useState<LoginState>("email");
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);

  useEffect(() => {
    if (isAuthenticated) {
      router.push("/");
    }
  }, [isAuthenticated, router]);

  // Check server health on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch("/api/health");
        const data = await response.json();
        setHealthStatus(data);
      } catch {
        setHealthStatus({
          status: "error",
          authMode: "direct",
          checks: {
            smtp: { configured: false, optional: true, error: "Cannot reach server" },
            adminApi: { configured: false, reachable: false, error: "Cannot reach server" },
            vexaApi: { configured: false, reachable: false, error: "Cannot reach server" },
          },
          missingConfig: [],
        });
      } finally {
        setHealthLoading(false);
      }
    };

    checkHealth();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email) {
      toast.error("Please enter your email");
      return;
    }

    const result = await sendMagicLink(email);

    if (result.success) {
      if (result.mode === "direct") {
        // Direct login mode - user is authenticated, redirect to dashboard
        toast.success(result.isNewUser ? "Account created! Welcome to Vexa." : "Welcome back!");
        router.push("/");
      } else {
        // Magic link mode - show "check your email" screen
        setState("sent");
        toast.success("Magic link sent! Check your email.");
      }
    } else {
      toast.error(result.error || "Failed to send magic link");
    }
  };

  const handleResend = async () => {
    const result = await sendMagicLink(email);

    if (result.success) {
      toast.success("Magic link sent again! Check your email.");
    } else {
      toast.error(result.error || "Failed to resend magic link");
    }
  };

  const handleBack = () => {
    setState("email");
  };

  const isConfigError = healthStatus?.status === "error";
  const hasWarnings = healthStatus?.status === "degraded";
  const isDirectMode = healthStatus?.authMode === "direct";

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-muted/30 p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex flex-col items-center justify-center gap-2 mb-8">
          <Logo size="lg" showText={true} />
          <p className="text-sm text-muted-foreground">Meeting Transcription</p>
        </div>

        {/* Configuration Error Banner */}
        {!healthLoading && isConfigError && (
          <div className="mb-4 p-4 rounded-lg bg-destructive/10 border border-destructive/20">
            <div className="flex items-start gap-3">
              <XCircle className="h-5 w-5 text-destructive mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <h3 className="font-medium text-destructive">Server Configuration Error</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  The server is not properly configured. Please contact the administrator.
                </p>
                {healthStatus?.missingConfig && healthStatus.missingConfig.length > 0 && (
                  <div className="mt-2 text-xs text-muted-foreground">
                    <span className="font-medium">Missing:</span> {healthStatus.missingConfig.join(", ")}
                  </div>
                )}
                {healthStatus?.checks.adminApi.error && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {healthStatus.checks.adminApi.error}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Warning Banner */}
        {!healthLoading && hasWarnings && (
          <div className="mb-4 p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-500 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <h3 className="font-medium text-yellow-600 dark:text-yellow-500">Connection Warning</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Some services may be unavailable. Login should still work.
                </p>
              </div>
            </div>
          </div>
        )}

        <Card className="border-0 shadow-xl">
          {state === "email" ? (
            <>
              <CardHeader className="text-center">
                <CardTitle className="text-xl">Welcome</CardTitle>
                <CardDescription>
                  {isDirectMode
                    ? "Enter your email to sign in"
                    : "Enter your email to receive a sign-in link"}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                      <Input
                        id="email"
                        type="email"
                        placeholder="you@example.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="pl-10"
                        disabled={isLoading || isConfigError}
                        autoFocus
                      />
                    </div>
                  </div>

                  <Button
                    type="submit"
                    className="w-full"
                    disabled={isLoading || healthLoading || isConfigError}
                  >
                    {healthLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Checking server...
                      </>
                    ) : isLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        {isDirectMode ? "Signing in..." : "Sending link..."}
                      </>
                    ) : isConfigError ? (
                      "Server Unavailable"
                    ) : isDirectMode ? (
                      "Sign In"
                    ) : (
                      "Send Magic Link"
                    )}
                  </Button>
                </form>
              </CardContent>
            </>
          ) : (
            <>
              <CardHeader className="text-center">
                <div className="flex justify-center mb-4">
                  <div className="h-16 w-16 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                    <CheckCircle className="h-8 w-8 text-green-600 dark:text-green-400" />
                  </div>
                </div>
                <CardTitle className="text-xl">Check your email</CardTitle>
                <CardDescription>
                  We sent a magic link to <span className="font-medium text-foreground">{email}</span>
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="bg-muted/50 rounded-lg p-4 text-sm text-muted-foreground">
                  <p className="mb-2">Click the link in the email to sign in.</p>
                  <p>The link will expire in 15 minutes.</p>
                </div>

                <div className="flex flex-col gap-2">
                  <Button
                    variant="outline"
                    onClick={handleResend}
                    disabled={isLoading}
                    className="w-full"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Sending...
                      </>
                    ) : (
                      "Resend magic link"
                    )}
                  </Button>

                  <Button
                    variant="ghost"
                    onClick={handleBack}
                    className="w-full"
                  >
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Use a different email
                  </Button>
                </div>
              </CardContent>
            </>
          )}
        </Card>

        <p className="text-center text-xs text-muted-foreground mt-6">
          Vexa Dashboard - Open Source Meeting Transcription
        </p>
      </div>
    </div>
  );
}
