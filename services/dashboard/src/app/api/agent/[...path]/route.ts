import { NextRequest } from "next/server";
import { cookies } from "next/headers";

const AGENT_API_URL = process.env.AGENT_API_URL || "http://localhost:8100";

async function getUserToken(): Promise<string> {
  const cookieStore = await cookies();
  return cookieStore.get("vexa-token")?.value || "";
}

export async function GET(req: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const url = new URL(req.url);
  const target = `${AGENT_API_URL}/api/${path.join("/")}${url.search}`;
  const resp = await fetch(target, {
    headers: { "Content-Type": "application/json" },
  });
  const data = await resp.json();
  return Response.json(data, { status: resp.status });
}

export async function POST(req: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const rawBody = await req.text();
  const target = `${AGENT_API_URL}/api/${path.join("/")}`;

  // For chat endpoint: inject user's bot token into request so agent container gets it
  if (path.join("/") === "chat") {
    const userToken = await getUserToken();
    let body = JSON.parse(rawBody);
    body.bot_token = userToken; // Agent API will pass this to the container

    const resp = await fetch(target, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    return new Response(resp.body, {
      status: resp.status,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  }

  const resp = await fetch(target, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: rawBody,
  });
  const data = await resp.json();
  return Response.json(data, { status: resp.status });
}

export async function PUT(req: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const body = await req.text();
  const target = `${AGENT_API_URL}/api/${path.join("/")}`;
  const resp = await fetch(target, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body,
  });
  const data = await resp.json();
  return Response.json(data, { status: resp.status });
}

export async function DELETE(req: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const body = await req.text();
  const target = `${AGENT_API_URL}/api/${path.join("/")}`;
  const resp = await fetch(target, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: body || undefined,
  });
  const data = await resp.json();
  return Response.json(data, { status: resp.status });
}
