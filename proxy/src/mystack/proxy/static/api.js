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
