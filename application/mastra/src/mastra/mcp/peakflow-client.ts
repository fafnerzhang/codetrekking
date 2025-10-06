import { MCPClient } from "@mastra/mcp";

/**
 * MCP Client for connecting to the PeakFlow API service
 *
 * This client connects to your FastAPI MCP server and provides access to fitness data tools and resources.
 * Uses NEXT_PUBLIC_API_URL environment variable for server configuration.
 */
const getApiBaseUrl = () => process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8010';

export const peakflowMcpClient = new MCPClient({
  id: "peakflow-api-client",
  servers: {
    peakflow: {
      url: new URL(`${getApiBaseUrl()}/mcp`),
      requestInit: {
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json, text/event-stream"
        }
      },
      // For SSE fallback with authentication
      eventSourceInit: {
        fetch(input: Request | URL | string, init?: RequestInit) {
          const headers = new Headers(init?.headers || {});

          // Add authorization header if available
          const token = process.env.PEAKFLOW_JWT_TOKEN;
          if (token) {
            headers.set("Authorization", `Bearer ${token}`);
          }

          return fetch(input, {
            ...init,
            headers
          });
        }
      },
      timeout: 30000,
      enableServerLogs: true
    }
  }
});

/**
 * Authenticate with PeakFlow API and get access token
 */
async function authenticateWithPeakflow(
  username: string,
  password: string,
  apiBaseUrl: string = getApiBaseUrl()
): Promise<string> {
  console.log("🔐 Authenticating with PeakFlow API...");

  const response = await fetch(`${apiBaseUrl}/api/v1/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ username, password })
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Authentication failed: ${response.status} ${errorText}`);
  }

  const data = await response.json();
  console.log("✅ Authentication successful");
  return data.access_token;
}

/**
 * Create authenticated MCP Client for PeakFlow API
 * This function handles authentication and creates the MCP client
 */
export async function createAuthenticatedPeakflowClient(
  username: string,
  password: string
) {
  // First authenticate to get the access token
  const accessToken = await authenticateWithPeakflow(username, password);

  return new MCPClient({
    id: `peakflow-api-client-${Date.now()}`,
    servers: {
      peakflow: {
        url: new URL(`${getApiBaseUrl()}/mcp`),
        requestInit: {
          headers: {
            "Authorization": `Bearer ${accessToken}`,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
          }
        },
        eventSourceInit: {
          fetch(input: Request | URL | string, init?: RequestInit) {
            const headers = new Headers(init?.headers || {});
            headers.set("Authorization", `Bearer ${accessToken}`);
            return fetch(input, {
              ...init,
              headers
            });
          }
        },
        timeout: 30000,
        enableServerLogs: true
      }
    }
  });
}

/**
 * Create MCP Client with existing access token
 */
export function createMcpClientWithToken(accessToken: string, apiBaseUrl: string = getApiBaseUrl(), apiPrefix: string = "/mcp") {
  console.log(`🔗 Creating MCP client for ${apiBaseUrl}${apiPrefix}`);
  
  return new MCPClient({
    id: `peakflow-api-client-${Date.now()}`,
    servers: {
      peakflow: {
        url: new URL(`${apiBaseUrl}${apiPrefix}`),
        requestInit: {
          headers: {
            "Authorization": `Bearer ${accessToken}`,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
          }
        },
        eventSourceInit: {
          fetch(input: Request | URL | string, init?: RequestInit) {
            const headers = new Headers(init?.headers || {});
            headers.set("Authorization", `Bearer ${accessToken}`);
            return fetch(input, {
              ...init,
              headers
            });
          }
        },
        timeout: 10000, // Reduced from 30s to 10s to prevent hangs
        enableServerLogs: true
      }
    }
  });
}