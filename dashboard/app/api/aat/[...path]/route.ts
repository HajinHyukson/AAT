import { NextRequest, NextResponse } from "next/server";

type RouteContext = {
  params: Promise<{
    path?: string[];
  }>;
};

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function HEAD(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function OPTIONS(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

async function proxyRequest(request: NextRequest, context: RouteContext) {
  const { path = [] } = await context.params;
  const targetUrl = buildTargetUrl(path, request.nextUrl.search);
  const headers = buildForwardHeaders(request);
  const init: RequestInit = {
    method: request.method,
    headers,
    cache: "no-store",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  const response = await fetch(targetUrl, init);
  return new NextResponse(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: buildResponseHeaders(response.headers),
  });
}

function buildTargetUrl(path: string[], search: string) {
  const baseUrl = process.env.AAT_API_BASE_URL ?? "http://127.0.0.1:8000";
  const url = new URL(baseUrl);
  const basePath = url.pathname.replace(/\/$/, "");
  const routePath = path.map(encodeURIComponent).join("/");
  url.pathname = [basePath, routePath].filter(Boolean).join("/");
  url.search = search;
  return url;
}

function buildForwardHeaders(request: NextRequest) {
  const headers = new Headers();
  const accept = request.headers.get("accept");
  const contentType = request.headers.get("content-type");
  const apiKey = process.env.AAT_API_KEY;

  if (accept) {
    headers.set("accept", accept);
  }
  if (contentType) {
    headers.set("content-type", contentType);
  }
  if (apiKey) {
    headers.set("x-aat-api-key", apiKey);
  }

  return headers;
}

function buildResponseHeaders(upstreamHeaders: Headers) {
  const headers = new Headers(upstreamHeaders);
  for (const header of HOP_BY_HOP_HEADERS) {
    headers.delete(header);
  }
  headers.set("cache-control", "no-store");
  return headers;
}
