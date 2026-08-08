/*
 * AWS JSON targets:
 * https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html
 * https://docs.aws.amazon.com/glue/latest/webapi/Welcome.html
 * Fetch contract: https://fetch.spec.whatwg.org/
 */

const TARGET_PREFIX = Object.freeze({
  emr: "ElasticMapReduce",
  glue: "AWSGlue",
});

export class ApiError extends Error {
  constructor(message, {code = "RequestFailed", requestId = null, status = 0, body = null} = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.requestId = requestId;
    this.status = status;
    this.body = body;
  }

  display() {
    const request = this.requestId ? `\nRequest ID: ${this.requestId}` : "";
    return `${this.code}: ${this.message}${request}`;
  }
}

export class MystackApi {
  constructor(tokenProvider) {
    this._tokenProvider = tokenProvider;
  }

  async components() {
    return this._json("/_mystack/components");
  }

  async resources(component) {
    return this._json(`/_mystack/components/${encodeURIComponent(component)}/resources`, {
      management: true,
    });
  }

  async logs(clusterId, stepId) {
    const query = new URLSearchParams({cluster_id: clusterId, step_id: stepId});
    return this._json(`/_mystack/components/emr/logs?${query}`, {management: true});
  }

  async streamLogs(clusterId, stepId, {
    stdoutOffset = 0,
    stderrOffset = 0,
    signal,
    onEvent,
  } = {}) {
    const query = new URLSearchParams({
      cluster_id: clusterId,
      step_id: stepId,
      stdout_offset: String(stdoutOffset),
      stderr_offset: String(stderrOffset),
    });
    const headers = {Accept: "text/event-stream"};
    const token = this._tokenProvider();
    if (token) headers.Authorization = `Bearer ${token}`;
    const response = await fetch(`/_mystack/components/emr/log-stream?${query}`, {
      headers,
      signal,
    });
    if (!response.ok || !response.body) {
      throw new ApiError(`EMR log stream returned HTTP ${response.status}`, {
        code: `HTTP${response.status}`,
        status: response.status,
      });
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let lastEventId = `${stdoutOffset}:${stderrOffset}`;
    let complete = false;
    while (true) {
      const {done, value} = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), {stream: !done}).replaceAll("\r\n", "\n");
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const event = parseSseBlock(block);
        if (!event) continue;
        if (event.id) lastEventId = event.id;
        if (event.type === "error") {
          throw new ApiError(event.data?.detail || "EMR log stream failed", {
            code: "LogStreamError",
            body: event.data,
          });
        }
        if (event.type === "logs") {
          complete = Boolean(event.data?.complete);
          onEvent?.(event.data, lastEventId);
        }
      }
      if (done) break;
    }
    return {lastEventId, complete};
  }

  async diagnostics(component, kind) {
    const root = component === "proxy"
      ? `/_mystack/diagnostics/${kind}`
      : `/_mystack/components/${encodeURIComponent(component)}/diagnostics/${kind}`;
    return this._json(root, {management: true});
  }

  async routes() {
    return this._json("/_mystack/routes");
  }

  async aws(service, operation, payload) {
    const prefix = TARGET_PREFIX[service];
    if (!prefix) throw new TypeError(`Unknown AWS JSON service: ${service}`);
    const response = await fetch("/", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": `${prefix}.${operation}`,
      },
      body: JSON.stringify(payload),
    });
    return this._document(response);
  }

  async _json(path, {management = false} = {}) {
    const headers = {};
    if (management) {
      const token = this._tokenProvider();
      if (token) headers.Authorization = `Bearer ${token}`;
    }
    const response = await fetch(path, {headers});
    return this._document(response);
  }

  async _document(response) {
    const requestId = response.headers.get("x-amzn-requestid");
    let body;
    try {
      body = await response.json();
    } catch {
      throw new ApiError(`HTTP ${response.status} returned a non-JSON response`, {
        status: response.status,
        requestId,
      });
    }
    if (!response.ok) {
      const rawCode = response.headers.get("x-amzn-errortype") || body.__type || body.code;
      const code = String(rawCode || `HTTP${response.status}`).split("#").at(-1).split(":")[0];
      throw new ApiError(body.Message || body.message || body.detail || response.statusText, {
        code,
        requestId,
        status: response.status,
        body,
      });
    }
    return body;
  }
}

function parseSseBlock(block) {
  if (!block || block.startsWith(":")) return null;
  let type = "message";
  let id = null;
  const data = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) type = line.slice(6).trimStart();
    else if (line.startsWith("id:")) id = line.slice(3).trimStart();
    else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return null;
  try {
    return {type, id, data: JSON.parse(data.join("\n"))};
  } catch {
    throw new ApiError("EMR log stream returned invalid JSON", {code: "LogStreamProtocolError"});
  }
}

export function lines(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map(item => item.trim())
    .filter(Boolean);
}

export function pairs(value, fieldName) {
  return lines(value).map((line, index) => {
    const separator = line.indexOf("=");
    if (separator < 1) {
      throw new ApiError(`${fieldName} line ${index + 1} must use key=value`, {
        code: "InvalidConsoleInput",
      });
    }
    return [line.slice(0, separator).trim(), line.slice(separator + 1).trim()];
  });
}
