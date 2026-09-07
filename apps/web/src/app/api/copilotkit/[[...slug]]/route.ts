import { NextRequest } from "next/server";

const apiUrl = process.env.AGENT_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  const body = await request.text();
  const response = await fetch(`${apiUrl}/api/agui`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "text/event-stream" },
    body,
  });
  return new Response(response.body, {
    status: response.status,
    headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
  });
}

export async function GET() {
  // CopilotKit runtime discovery expects an agents map, even in static mode.
  return Response.json({
    version: "0.1.0",
    mode: "sse",
    agents: {
      default: { description: "Bedashing grounded portfolio analyst", capabilities: [] },
    },
  });
}
