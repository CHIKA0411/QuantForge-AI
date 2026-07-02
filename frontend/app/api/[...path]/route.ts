import { NextRequest, NextResponse } from "next/server";

const BACKEND_BASE = process.env.BACKEND_URL || "http://localhost:8000/api";

/**
 * Catch-all proxy route: forwards any /api/* request from the browser
 * to the FastAPI backend server-side, bypassing Chrome extension interference.
 */
async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const pathStr = path.join("/");

  // Forward original query string
  const searchParams = request.nextUrl.searchParams.toString();
  const targetUrl = `${BACKEND_BASE}/${pathStr}${searchParams ? `?${searchParams}` : ""}`;

  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    // Forward body for non-GET requests
    let body: string | undefined;
    if (request.method !== "GET" && request.method !== "HEAD") {
      body = await request.text();
    }

    const backendRes = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
    });

    const data = await backendRes.json();

    return NextResponse.json(data, { status: backendRes.status });
  } catch (err) {
    console.error(`[Proxy] Failed to reach backend at ${targetUrl}:`, err);
    return NextResponse.json(
      { error: "Backend unreachable", detail: String(err) },
      { status: 502 }
    );
  }
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const DELETE = handler;
export const PATCH = handler;
