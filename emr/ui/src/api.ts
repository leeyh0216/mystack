/**
 * EMR UI adapter. Mutations match official AWS JSON operation names and share the boto3 endpoint:
 * https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html
 * SSE framing: https://html.spec.whatwg.org/multipage/server-sent-events.html
 */
import {awsJson, requestJson} from "@mystack/ui";
import type {EmrLogChunk, EmrLogs, EmrResourceDocument, UiConfig} from "./types";

const UI_BASE = "/_mystack/ui/emr/";

export class EmrUiApi {
  resources(): Promise<EmrResourceDocument> { return requestJson("resources", UI_BASE); }
  config(): Promise<UiConfig> { return requestJson("config", UI_BASE); }
  logs(clusterId: string, stepId: string): Promise<EmrLogs> {
    return requestJson(`logs?${new URLSearchParams({cluster_id: clusterId, step_id: stepId})}`, UI_BASE);
  }
  diagnostics(kind: "threads" | "tasks"): Promise<unknown> { return requestJson(`diagnostics/${kind}`, UI_BASE); }
  mutation<T>(operation: string, payload: unknown): Promise<T> { return awsJson("ElasticMapReduce", operation, payload); }

  async streamLogs(
    clusterId: string,
    stepId: string,
    offsets: {stdout: number; stderr: number},
    signal: AbortSignal,
    onChunk: (value: EmrLogChunk) => void,
  ): Promise<boolean> {
    const query = new URLSearchParams({
      cluster_id: clusterId,
      step_id: stepId,
      stdout_offset: String(offsets.stdout),
      stderr_offset: String(offsets.stderr),
    });
    const response = await fetch(new URL(`log-stream?${query}`, new URL(UI_BASE, window.location.origin)), {
      headers: {Accept: "text/event-stream"},
      signal,
    });
    if (!response.ok || !response.body) throw new Error(`EMR log stream returned HTTP ${response.status}`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let complete = false;
    while (true) {
      const result = await reader.read();
      buffer += decoder.decode(result.value || new Uint8Array(), {stream: !result.done}).replaceAll("\r\n", "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const event = parseEvent(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        if (event) {
          if (event.type === "error") throw new Error(String((event.data as {detail?: string}).detail || "Log stream failed"));
          if (event.type === "logs") {
            const chunk = event.data as EmrLogChunk;
            complete = chunk.complete;
            onChunk(chunk);
          }
        }
        boundary = buffer.indexOf("\n\n");
      }
      if (result.done) return complete;
    }
  }
}

function parseEvent(block: string): {type: string; data: unknown} | null {
  if (!block || block.startsWith(":")) return null;
  let type = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) type = line.slice(6).trim();
    if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  return data.length ? {type, data: JSON.parse(data.join("\n"))} : null;
}
