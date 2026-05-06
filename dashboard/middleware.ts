import { NextRequest, NextResponse } from "next/server";

const REALM = "AAT Dashboard";

export function middleware(request: NextRequest) {
  const expectedUser = process.env.AAT_DASHBOARD_USER;
  const expectedPassword = process.env.AAT_DASHBOARD_PASSWORD;

  if (!expectedUser || !expectedPassword) {
    return NextResponse.next();
  }

  const credentials = parseBasicAuth(request.headers.get("authorization"));
  if (
    credentials &&
    credentials.username === expectedUser &&
    credentials.password === expectedPassword
  ) {
    return NextResponse.next();
  }

  return new NextResponse("Authentication required", {
    status: 401,
    headers: {
      "WWW-Authenticate": `Basic realm="${REALM}", charset="UTF-8"`,
    },
  });
}

function parseBasicAuth(value: string | null) {
  if (!value?.startsWith("Basic ")) {
    return null;
  }

  try {
    const decoded = atob(value.slice("Basic ".length));
    const separator = decoded.indexOf(":");
    if (separator < 0) {
      return null;
    }
    return {
      username: decoded.slice(0, separator),
      password: decoded.slice(separator + 1),
    };
  } catch {
    return null;
  }
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|icon.svg).*)"],
};
