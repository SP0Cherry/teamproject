import { attemptRefresh, getAccessToken } from "./client";

export interface SseHandlers {
  onEvent?: (event: string, data: any) => void;
  onError?: (code: string, message: string) => void;
  onDone?: () => void;
}

/**
 * POST to an SSE endpoint and dispatch parsed events. Uses fetch (not
 * EventSource) so we can send a JSON body and the Bearer token. On a 401 the
 * access token is refreshed once and the request retried (SEC-05/SEC-06).
 */
export async function postSSE(
  path: string,
  body: unknown,
  handlers: SseHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const baseURL = import.meta.env.VITE_API_BASE || "/api/v1";

  const doFetch = (token: string | null): Promise<Response> =>
    fetch(`${baseURL}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
      signal,
    });

  let resp: Response;
  try {
    resp = await doFetch(getAccessToken());
  } catch {
    handlers.onError?.("NETWORK_ERROR", "网络异常，请重试");
    return;
  }

  // Access token expired: refresh once (coordinated) and retry.
  if (resp.status === 401) {
    const refreshed = await attemptRefresh();
    if (refreshed) {
      try {
        resp = await doFetch(getAccessToken());
      } catch {
        handlers.onError?.("NETWORK_ERROR", "网络异常，请重试");
        return;
      }
    }
  }

  if (!resp.ok || !resp.body) {
    let code = "NETWORK_ERROR";
    let message = `请求失败 (${resp.status})`;
    try {
      const errBody = await resp.json();
      if (errBody && typeof errBody.code === "string") {
        code = errBody.code;
        message = errBody.message || message;
      }
    } catch {
      // response body is not JSON; keep the generic message
    }
    handlers.onError?.(code, message);
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (frame: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }
    const raw = dataLines.join("\n");
    let data: any = raw;
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      // keep raw string
    }
    if (event === "error") {
      handlers.onError?.(data?.code || "ERROR", data?.message || "");
    } else if (event === "done") {
      handlers.onDone?.();
    } else {
      handlers.onEvent?.(event, data);
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx = buffer.indexOf("\n\n");
    while (idx !== -1) {
      dispatch(buffer.slice(0, idx));
      buffer = buffer.slice(idx + 2);
      idx = buffer.indexOf("\n\n");
    }
  }
}
