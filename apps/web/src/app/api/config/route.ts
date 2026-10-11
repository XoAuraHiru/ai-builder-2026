import { NextResponse } from "next/server";

// Read at request time so Cloud Run environment variables apply without a rebuild.
export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({
    apiUrl: process.env.API_URL ?? "http://localhost:8000",
    authMode: process.env.AUTH_MODE ?? "dev",
    firebase: {
      apiKey: process.env.FIREBASE_API_KEY ?? "",
      authDomain: process.env.FIREBASE_AUTH_DOMAIN ?? "",
      projectId: process.env.FIREBASE_PROJECT_ID ?? "",
      appId: process.env.FIREBASE_APP_ID ?? "",
    },
  });
}
