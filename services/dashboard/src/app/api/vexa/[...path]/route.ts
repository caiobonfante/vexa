import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

async function proxyRequest(
  request: NextRequest,
  params: Promise<{ path: string[] }>,
  method: string
): Promise<NextResponse> {
  const VEXA_API_URL = process.env.VEXA_API_URL || "http://localhost:8066";

  // Get user's token from HTTP-only cookie (set during login)
  const cookieStore = await cookies();
  const userToken = cookieStore.get("vexa-token")?.value;

  // Fall back to env variable for backwards compatibility
  const VEXA_API_KEY = userToken || process.env.VEXA_API_KEY || "";

  const { path } = await params;
  let pathString = path.join("/");

  // /meetings list: api-gateway doesn't have a combined list endpoint,
  // so we build it from /bots/status + /meetings (TC)
  if (pathString === "meetings" && method === "GET") {
    const meetings: any[] = [];
    const seenIds = new Set<string>();

    // 1. Active bots from api-gateway → bot-manager
    try {
      const statusResp = await fetch(`${VEXA_API_URL}/bots/status`, {
        headers: { "X-API-Key": VEXA_API_KEY },
      });
      if (statusResp.ok) {
        const data = await statusResp.json();
        for (const b of data.running_bots || []) {
          const id = b.meeting_id_from_name || b.container_name;
          seenIds.add(id);
          meetings.push({
            id: parseInt(id) || 0,
            platform: b.platform,
            native_meeting_id: b.native_meeting_id,
            status: "active",
            start_time: b.created_at,
            end_time: null,
            bot_container_id: b.container_id,
            data: {},
            created_at: b.created_at,
          });
        }
      }
    } catch {}

    // 2. Meeting history from api-gateway → TC
    try {
      const tcResp = await fetch(`${VEXA_API_URL}/meetings`, {
        headers: { "X-API-Key": VEXA_API_KEY },
        signal: AbortSignal.timeout(5000),
      });
      if (tcResp.ok) {
        const tcData = await tcResp.json();
        const tcMeetings = Array.isArray(tcData) ? tcData : tcData.meetings || [];
        for (const m of tcMeetings) {
          const id = (m.id || "").toString();
          if (seenIds.has(id)) continue;
          seenIds.add(id);
          meetings.push({
            id: m.id,
            platform: m.platform,
            native_meeting_id: m.native_meeting_id || m.platform_specific_id,
            status: m.status || "completed",
            start_time: m.start_time,
            end_time: m.end_time,
            bot_container_id: null,
            data: m.data || {},
            created_at: m.created_at || m.start_time,
          });
        }
      }
    } catch {}

    return NextResponse.json({ meetings });
  }

  // Everything else: proxy through api-gateway (handles /transcripts, /recordings, /bots, etc.)
  const searchParams = request.nextUrl.searchParams.toString();
  const url = `${VEXA_API_URL}/${pathString}${searchParams ? `?${searchParams}` : ""}`;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };

  if (VEXA_API_KEY) {
    headers["X-API-Key"] = VEXA_API_KEY;
  }

  const rangeHeader = request.headers.get("range");
  if (rangeHeader) {
    headers["Range"] = rangeHeader;
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    const fetchOptions: RequestInit = {
      method,
      headers,
      signal: controller.signal,
    };

    if (method !== "GET" && method !== "HEAD") {
      const body = await request.text();
      if (body) {
        fetchOptions.body = body;
      }
    }

    const response = await fetch(url, fetchOptions);
    clearTimeout(timeoutId);

    const contentType = response.headers.get("content-type") || "";

    if (contentType.includes("audio") || contentType.includes("video") || contentType.includes("octet-stream")) {
      const blob = await response.blob();
      return new NextResponse(blob, {
        status: response.status,
        headers: {
          "Content-Type": contentType,
          "Content-Length": response.headers.get("content-length") || "",
          ...(response.headers.get("content-range") && {
            "Content-Range": response.headers.get("content-range")!,
          }),
          ...(response.headers.get("accept-ranges") && {
            "Accept-Ranges": response.headers.get("accept-ranges")!,
          }),
        },
      });
    }

    const data = await response.text();
    try {
      return NextResponse.json(JSON.parse(data), { status: response.status });
    } catch {
      return new NextResponse(data, {
        status: response.status,
        headers: { "Content-Type": contentType },
      });
    }
  } catch (error) {
    const err = error as Error;
    if (err.name === "AbortError") {
      return NextResponse.json({ error: "Request timeout" }, { status: 504 });
    }
    return NextResponse.json(
      { error: `Failed to connect to API: ${err.message}` },
      { status: 502 }
    );
  }
}

export async function GET(req: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(req, context.params, "GET");
}

export async function POST(req: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(req, context.params, "POST");
}

export async function PUT(req: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(req, context.params, "PUT");
}

export async function DELETE(req: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(req, context.params, "DELETE");
}
