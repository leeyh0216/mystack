/** EMR log locations: https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html */
import {Alert, Badge, Button, JsonView, LoadingState} from "@mystack/ui";
import {useCallback, useEffect, useRef, useState} from "react";
import type {EmrUiApi} from "./api";
import type {EmrCluster, EmrLogChunk, EmrLogs, EmrStep} from "./types";

const ACTIVE = new Set(["PENDING", "CANCEL_PENDING", "RUNNING"]);

export function StepLogs({api, cluster, step, bufferBytes, onCancel}: {api: EmrUiApi; cluster: EmrCluster; step: EmrStep; bufferBytes: number; onCancel: () => Promise<void>}) {
  const [snapshot, setSnapshot] = useState<EmrLogs | null>(null);
  const [stdout, setStdout] = useState("");
  const [stderr, setStderr] = useState("");
  const [offsets, setOffsets] = useState({stdout: 0, stderr: 0});
  const offsetsRef = useRef(offsets);
  const [paused, setPaused] = useState(false);
  const [complete, setComplete] = useState(false);
  const [status, setStatus] = useState("Connecting…");
  const [error, setError] = useState<Error | null>(null);

  const append = useCallback((chunk: EmrLogChunk) => {
    const next = {stdout: chunk.stdout_next_offset, stderr: chunk.stderr_next_offset};
    offsetsRef.current = next;
    setOffsets(next);
    setStdout(value => bounded(value + (chunk.stdout || ""), bufferBytes));
    setStderr(value => bounded(value + (chunk.stderr || ""), bufferBytes));
    setSnapshot(value => value ? {...value, step_state: chunk.step_state, log_publication: chunk.log_publication} : value);
    setComplete(chunk.complete);
    if (chunk.complete) setStatus("Complete");
  }, [bufferBytes]);

  useEffect(() => {
    let disposed = false;
    const controller = new AbortController();
    setSnapshot(null); setStdout(""); setStderr(""); setOffsets({stdout: 0, stderr: 0}); offsetsRef.current = {stdout: 0, stderr: 0}; setComplete(false); setPaused(false); setError(null);
    void api.logs(cluster.id, step.id).then(value => { if (!disposed) setSnapshot(value); }).catch(caught => { if (!disposed) setError(asError(caught)); });
    return () => { disposed = true; controller.abort(); };
  }, [api, cluster.id, step.id]);

  useEffect(() => {
    if (paused || complete) return;
    const controller = new AbortController();
    let retry: number | undefined;
    setStatus("Following live output");
    const follow = async () => {
      try {
        const done = await api.streamLogs(cluster.id, step.id, offsetsRef.current, controller.signal, append);
        if (done) { setComplete(true); setStatus("Complete"); }
        else if (!controller.signal.aborted) { setStatus("Reconnecting…"); retry = window.setTimeout(() => void follow(), 500); }
      } catch (caught) {
        if (controller.signal.aborted) return;
        setError(asError(caught));
        setStatus("Stream interrupted · retrying");
        retry = window.setTimeout(() => void follow(), 500);
      }
    };
    void follow();
    return () => { controller.abort(); if (retry) window.clearTimeout(retry); };
  }, [api, append, cluster.id, step.id, paused, complete]);

  const download = () => {
    const content = `Mystack EMR Step ${step.id}\n\n===== stdout =====\n${stdout}\n\n===== stderr =====\n${stderr}\n`;
    const url = URL.createObjectURL(new Blob([content], {type: "text/plain;charset=utf-8"}));
    const link = document.createElement("a"); link.href = url; link.download = `${step.id}-logs.txt`; link.click(); URL.revokeObjectURL(url);
  };
  return <div className="grid gap-5">
    <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
      <div className="min-w-0"><h3 className="break-words text-lg font-bold">{step.name}</h3><p id="logStepIdentity" className="break-all font-mono text-xs text-ink-muted">{step.id} · {snapshot?.step_state || step.state}{step.recovered ? " · recovered logs" : ""}</p></div>
      <div className="flex flex-wrap items-center gap-2"><Badge tone={complete ? "positive" : paused ? "warning" : "info"}><span id="logFollowStatus">{paused ? "Paused" : status}</span></Badge>{(snapshot?.step_state || step.state) === "RUNNING" ? <a id="openSparkUi" className="rounded bg-brand px-3 py-2 text-sm font-semibold text-white" href={`/_mystack/ui/emr/spark/${cluster.id}/${step.id}/`}>Open Spark UI</a> : null}<Button id="toggleLogFollow" disabled={complete} onClick={() => setPaused(value => !value)}>{paused ? "Resume follow" : "Pause follow"}</Button><Button id="downloadLogs" onClick={download}>Download</Button><Button id="cancelStep" variant="danger" disabled={!ACTIVE.has(snapshot?.step_state || step.state)} onClick={() => void onCancel()}>Cancel Step</Button></div>
    </div>
    {error && <Alert>{error.message}</Alert>}
    {!snapshot ? <LoadingState label="Loading Step logs" /> : <>
      <section className="grid min-w-0 gap-3 xl:grid-cols-2"><div className="min-w-0"><h3 className="mb-2 text-sm font-bold">Submitted HadoopJarStep</h3><JsonView value={{Jar: step.jar, MainClass: step.main_class, Args: step.args, Properties: step.properties}} id="submittedCommand" /></div><div className="min-w-0"><h3 className="mb-2 text-sm font-bold">Resolved local process argv</h3><JsonView value={snapshot.resolved_command} id="resolvedCommand" /></div></section>
      <section><h3 className="mb-2 text-sm font-bold">S3 LogUri publication</h3><div id="logPublication"><JsonView value={snapshot.log_publication} /></div></section>
      <div className="grid gap-4 xl:grid-cols-2"><LogPane id="stdout" title="stdout" value={stdout} /><LogPane id="stderr" title="stderr" value={stderr} /></div>
    </>}
  </div>;
}

function LogPane({id, title, value}: {id: string; title: string; value: string}) {
  const ref = useRef<HTMLPreElement>(null);
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [value]);
  return <section><h4 className="mb-2 text-sm font-bold">{title}</h4><pre ref={ref} id={id} tabIndex={0} className="h-80 overflow-auto rounded-control bg-code p-4 font-mono text-xs leading-5 whitespace-pre-wrap break-words text-code-ink">{value || "(waiting for output)"}</pre></section>;
}

function bounded(value: string, byteLimit: number): string {
  const encoder = new TextEncoder();
  if (encoder.encode(value).byteLength <= byteLimit) return value;
  const notice = `[older output removed; ${byteLimit} byte browser limit]\n`;
  let tail = value.slice(-Math.max(1, byteLimit - encoder.encode(notice).byteLength));
  while (encoder.encode(notice + tail).byteLength > byteLimit) tail = tail.slice(Math.max(1, Math.floor(tail.length / 20)));
  return notice + tail;
}

function asError(value: unknown): Error { return value instanceof Error ? value : new Error(String(value)); }
