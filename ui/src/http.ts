/**
 * Service-relative UI HTTP boundary. AWS mutations intentionally use the same public root JSON
 * endpoint as boto3. Fetch reference: https://fetch.spec.whatwg.org/
 */
export class ApiError extends Error {
  readonly code: string;
  readonly requestId: string | null;
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, options: {code?: string; requestId?: string | null; status?: number; body?: unknown} = {}) {
    super(message);
    this.name = "ApiError";
    this.code = options.code || "RequestFailed";
    this.requestId = options.requestId || null;
    this.status = options.status || 0;
    this.body = options.body;
  }

  display(): string {
    return `${this.code}: ${this.message}${this.requestId ? `\nRequest ID: ${this.requestId}` : ""}`;
  }
}

export async function requestJson<T>(relativePath: string, serviceBasePath: string, init?: RequestInit): Promise<T> {
  const normalizedBase = serviceBasePath.endsWith("/") ? serviceBasePath : `${serviceBasePath}/`;
  const response = await fetch(new URL(relativePath, new URL(normalizedBase, window.location.origin)), init);
  return responseDocument<T>(response);
}

export async function awsJson<T>(targetPrefix: "ElasticMapReduce" | "AWSGlue", operation: string, payload: unknown): Promise<T> {
  const response = await fetch(new URL("/", window.location.origin), {
    method: "POST",
    headers: {
      "Content-Type": "application/x-amz-json-1.1",
      "X-Amz-Target": `${targetPrefix}.${operation}`,
    },
    body: JSON.stringify(payload),
  });
  return responseDocument<T>(response);
}

async function responseDocument<T>(response: Response): Promise<T> {
  const requestId = response.headers.get("x-amzn-requestid");
  let body: Record<string, unknown>;
  try {
    body = await response.json() as Record<string, unknown>;
  } catch {
    throw new ApiError(`HTTP ${response.status} returned a non-JSON response`, {status: response.status, requestId});
  }
  if (!response.ok) {
    const rawCode = response.headers.get("x-amzn-errortype") || body.__type || body.code;
    const code = String(rawCode || `HTTP${response.status}`).split("#").at(-1)?.split(":")[0];
    throw new ApiError(String(body.Message || body.message || body.detail || response.statusText), {
      code,
      requestId,
      status: response.status,
      body,
    });
  }
  return body as T;
}

export function lines(value: FormDataEntryValue | null): string[] {
  return String(value || "").split(/\r?\n/).map(item => item.trim()).filter(Boolean);
}

export function pairs(value: FormDataEntryValue | null, fieldName: string): Array<[string, string]> {
  return lines(value).map((line, index) => {
    const separator = line.indexOf("=");
    if (separator < 1) throw new ApiError(`${fieldName} line ${index + 1} must use key=value`, {code: "InvalidConsoleInput"});
    return [line.slice(0, separator).trim(), line.slice(separator + 1).trim()];
  });
}
