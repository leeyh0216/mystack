/**
 * Service-owned EMR application assembled from @mystack/ui primitives.
 * EMR operation reference: https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html
 */
import {
  Alert,
  ApiError,
  AppShell,
  Badge,
  Button,
  DefinitionGrid,
  EmptyState,
  Input,
  JsonView,
  LoadingState,
  Panel,
  PanelHeader,
  SummaryCard,
  Table,
  TableBody,
  TableCell,
  TableFrame,
  TableHead,
  TableHeaderCell,
  TableRow,
  Tabs,
  useBrowserRoute,
  usePollingResource,
} from "@mystack/ui";
import {useCallback, useEffect, useState} from "react";
import {EmrUiApi} from "./api";
import {AddStepDialog, CreateClusterDialog} from "./forms";
import {StepLogs} from "./logs";
import {formatEmrRoute, parseEmrRoute, rootEmrRoute, type EmrTab} from "./routes";
import type {EmrCluster, EmrResourceDocument, EmrStep, UiConfig} from "./types";

const api = new EmrUiApi();
const TERMINAL_CLUSTERS = new Set(["TERMINATED", "TERMINATED_WITH_ERRORS"]);
const ACTIVE_STEPS = new Set(["PENDING", "CANCEL_PENDING", "RUNNING"]);
const FALLBACK_UI_CONFIG: UiConfig = {refresh_interval_seconds: 2, log_stream_poll_interval_seconds: 0.5, log_stream_timeout_seconds: 300, log_buffer_bytes: 1_048_576};

export default function App() {
  const [config, setConfig] = useState(FALLBACK_UI_CONFIG);
  const {route, navigate} = useBrowserRoute("/_mystack/ui/emr", parseEmrRoute, formatEmrRoute);
  const [clusterDialog, setClusterDialog] = useState(false);
  const [stepDialog, setStepDialog] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<Error | null>(null);
  const load = useCallback(() => api.resources(), []);
  const resource = usePollingResource<EmrResourceDocument>(load, config.refresh_interval_seconds * 1000);

  useEffect(() => { void api.config().then(setConfig).catch(setMutationError); }, []);
  useEffect(() => {
    if (!resource.data) return;
    const selectedCluster = resource.data.resources.clusters.find(cluster => cluster.id === route.clusterId);
    if (route.clusterId && !selectedCluster) {
      navigate(rootEmrRoute(), true);
    } else if (route.stepId && selectedCluster && !selectedCluster.steps.some(step => step.id === route.stepId)) {
      navigate({clusterId: selectedCluster.id, stepId: null, tab: "steps"}, true);
    }
  }, [navigate, resource.data, route.clusterId, route.stepId]);

  const clusters = resource.data?.resources.clusters || [];
  const cluster = clusters.find(value => value.id === route.clusterId) || null;
  const step = cluster?.steps.find(value => value.id === route.stepId) || null;

  const mutate = async (operation: string, payload: unknown, message: string) => {
    setMutationError(null); setNotice(`${message}…`);
    try {
      const value = await api.mutation<Record<string, unknown>>(operation, payload);
      setNotice(message);
      await resource.refresh();
      return value;
    } catch (caught) {
      const error = asError(caught); setMutationError(error); setNotice(null); throw error;
    }
  };

  const createCluster = async (payload: unknown) => {
    const result = await mutate("RunJobFlow", payload, "Cluster created");
    navigate({clusterId: String(result.JobFlowId), stepId: null, tab: "overview"}); setClusterDialog(false);
  };
  const addStep = async (value: {name: string; action: string; hadoop: Record<string, unknown>}) => {
    if (!cluster) return;
    const result = await mutate("AddJobFlowSteps", {JobFlowId: cluster.id, Steps: [{Name: value.name, ActionOnFailure: value.action, HadoopJarStep: value.hadoop}]}, "Step submitted");
    const ids = result.StepIds as string[];
    navigate({clusterId: cluster.id, stepId: ids[0], tab: "logs"}); setStepDialog(false);
  };
  const terminate = async () => {
    if (!cluster || !window.confirm(`Terminate cluster ${cluster.name} (${cluster.id})?`)) return;
    await mutate("TerminateJobFlows", {JobFlowIds: [cluster.id]}, "Termination submitted");
  };
  const protect = async () => {
    if (!cluster) return;
    await mutate("SetTerminationProtection", {JobFlowIds: [cluster.id], TerminationProtected: !cluster.termination_protected}, "Termination protection updated");
  };
  const cancel = async () => {
    if (!cluster || !step) return;
    await mutate("CancelSteps", {ClusterId: cluster.id, StepIds: [step.id]}, "Step cancellation submitted");
  };

  const status = resource.error || mutationError ? "Attention required" : resource.busy ? "Refreshing…" : notice || (resource.updatedAt ? `Updated ${resource.updatedAt.toLocaleTimeString()}` : "Starting…");
  return <AppShell
    service="Amazon EMR"
    homeHref="/_mystack/ui/emr/"
    title="Clusters"
    description="Create local Spark clusters, submit Steps, follow live output, and inspect durable S3 log publication."
    status={status}
    navigation={<><a aria-current="page" className="rounded-control bg-white/12 px-3 py-1.5 text-sm font-bold text-white" href="/_mystack/ui/emr/">EMR</a><a className="rounded-control px-3 py-1.5 text-sm text-code-ink/75 hover:bg-white/10 hover:text-white" href="/_mystack/ui/glue/">Glue</a></>}
    actions={<><Button onClick={() => void resource.refresh()} disabled={resource.busy}>Refresh</Button><Button variant="primary" onClick={() => setClusterDialog(true)}>Create cluster</Button></>}
  >
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <SummaryCard label="Mode" value={resource.data?.emulator.mode || "Spark local mode"} />
      <SummaryCard label="Compatibility" value={resource.data ? `${resource.data.compatibility.classification} · ${resource.data.compatibility.implemented_operation_count}/${resource.data.compatibility.model_operation_count}` : "—"} />
      <SummaryCard label="Clusters" value={resource.data?.counts.clusters ?? "—"} />
      <SummaryCard label="Steps" value={resource.data?.counts.steps ?? "—"} />
    </div>
    {resource.data?.emulator.notice && <p className="mt-3 text-sm text-ink-muted">{resource.data.emulator.notice}</p>}
    {(resource.error || mutationError) && <div className="mt-4"><Alert>{displayError(resource.error || mutationError)}</Alert></div>}
    {!resource.data ? <LoadingState label="Loading EMR clusters" /> : <div className="mt-5 grid min-w-0 gap-5 lg:grid-cols-[22rem_minmax(0,1fr)]">
      <ClusterList clusters={clusters} selectedId={route.clusterId} onSelect={value => navigate({clusterId: value, stepId: null, tab: "overview"})} />
      <Panel className="min-w-0 overflow-hidden">
        {!cluster ? <EmptyState title="Select a cluster" description="Choose a cluster to inspect configuration, Steps, timelines, live logs, and diagnostics." /> : <ClusterDetail
          api={api}
          cluster={cluster}
          step={step}
          activeTab={route.tab}
          onTab={(tab: EmrTab) => navigate({clusterId: cluster.id, stepId: tab === "logs" ? route.stepId : null, tab})}
          onStep={value => navigate({clusterId: cluster.id, stepId: value.id, tab: "logs"})}
          onAddStep={() => setStepDialog(true)}
          onProtect={() => void protect()}
          onTerminate={() => void terminate()}
          onCancel={cancel}
          bufferBytes={config.log_buffer_bytes}
        />}
      </Panel>
    </div>}
    <CreateClusterDialog open={clusterDialog} releaseProfiles={resource.data?.emulator.release_profiles || {}} defaultRelease={resource.data?.emulator.default_release_label || ""} onClose={() => setClusterDialog(false)} onSubmit={createCluster} />
    <AddStepDialog open={stepDialog} commandAliases={cluster ? resource.data?.emulator.release_profiles[cluster.release_label]?.submit_aliases || [] : []} onClose={() => setStepDialog(false)} onSubmit={addStep} />
  </AppShell>;
}

function ClusterList({clusters, selectedId, onSelect}: {clusters: EmrCluster[]; selectedId: string | null; onSelect: (id: string) => void}) {
  const [query, setQuery] = useState("");
  const values = clusters.filter(cluster => `${cluster.name} ${cluster.id} ${cluster.state}`.toLowerCase().includes(query.toLowerCase()));
  return <Panel className="overflow-hidden"><PanelHeader eyebrow="EMR" title="Clusters" actions={<Badge>{clusters.length}</Badge>} /><div className="p-4"><Input label="Filter clusters" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Name, ID, or state" /><div className="mt-3 grid max-h-[55rem] gap-2 overflow-y-auto" role="list">{values.length ? values.map(cluster => <button key={cluster.id} type="button" aria-label={`Cluster ${cluster.name}`} aria-current={cluster.id === selectedId ? "true" : undefined} className={`flex min-w-0 items-center justify-between gap-3 rounded-control border p-3 text-left transition ${cluster.id === selectedId ? "border-brand bg-brand/8" : "border-border bg-surface hover:bg-surface-muted"}`} onClick={() => onSelect(cluster.id)}><span className="min-w-0"><strong className="block truncate text-sm">{cluster.name}</strong><small className="block truncate font-mono text-xs text-ink-muted">{cluster.id}</small></span><StateBadge state={cluster.state} /></button>) : <p className="p-4 text-center text-sm text-ink-muted">{clusters.length ? "No matching clusters" : "No clusters yet"}</p>}</div></div></Panel>;
}

function ClusterDetail({api, cluster, step, activeTab, onTab, onStep, onAddStep, onProtect, onTerminate, onCancel, bufferBytes}: {api: EmrUiApi; cluster: EmrCluster; step: EmrStep | null; activeTab: EmrTab; onTab: (tab: EmrTab) => void; onStep: (step: EmrStep) => void; onAddStep: () => void; onProtect: () => void; onTerminate: () => void; onCancel: () => Promise<void>; bufferBytes: number}) {
  const terminal = TERMINAL_CLUSTERS.has(cluster.state);
  return <><PanelHeader eyebrow={cluster.recovered ? "Recovered log-only cluster" : "Cluster detail"} title={cluster.name} actions={<><Button variant="primary" disabled={!(["WAITING", "RUNNING"].includes(cluster.state))} onClick={onAddStep}>Add Step</Button><Button disabled={terminal || cluster.recovered} onClick={onProtect}>{cluster.termination_protected ? "Unprotect" : "Protect"}</Button><Button variant="danger" disabled={terminal || cluster.recovered} onClick={onTerminate}>Terminate</Button></>} /><div className="p-5"><p className="mb-4 break-all font-mono text-xs text-ink-muted">{cluster.id}</p><DefinitionGrid items={[["State", <StateBadge key="state" state={cluster.state} />], ["Release", cluster.release_label], ["Log URI", cluster.log_uri || "Not configured"], ["Step concurrency", cluster.step_concurrency_level], ["Termination protected", cluster.termination_protected ? "Yes" : "No"], ["Created", formatTime(cluster.created_at)]]} /></div><Tabs label="Cluster detail views" active={activeTab} onChange={value => onTab(value as EmrTab)} tabs={[
    {id: "overview", label: "Overview", panel: <Overview cluster={cluster} />},
    {id: "steps", label: "Steps", panel: <Steps cluster={cluster} selected={step?.id || null} onSelect={onStep} />},
    {id: "logs", label: "Logs", panel: step ? <StepLogs api={api} cluster={cluster} step={step} bufferBytes={bufferBytes} onCancel={onCancel} /> : <EmptyState title="Select a Step" description="Choose a Step from the Steps tab to inspect live stdout, stderr, and S3 publication." />},
    {id: "diagnostics", label: "Diagnostics", panel: <Diagnostics api={api} />},
    {id: "raw", label: "Raw detail", panel: <JsonView value={cluster} id="emrRaw" />},
  ]} /></>;
}

function Overview({cluster}: {cluster: EmrCluster}) {
  return <div className="grid gap-6 xl:grid-cols-2"><section><h3 className="mb-2 font-bold">Bootstrap actions</h3>{cluster.bootstrap_actions.length ? <ul className="grid gap-2 text-sm">{cluster.bootstrap_actions.map(action => <li key={`${action.name}-${action.path}`} className="rounded-control bg-surface-muted p-3"><strong>{action.name}</strong><p className="break-all font-mono text-xs text-ink-muted">{action.path} · {action.argument_count} args</p></li>)}</ul> : <p className="text-sm text-ink-muted">No bootstrap actions</p>}</section><section><h3 className="mb-2 font-bold">Tags</h3>{Object.keys(cluster.tags).length ? <JsonView value={cluster.tags} /> : <p className="text-sm text-ink-muted">No tags</p>}</section><section className="xl:col-span-2"><h3 className="mb-2 font-bold">Timeline</h3><DefinitionGrid items={[["Created", formatTime(cluster.created_at)], ["Ready", formatTime(cluster.ready_at)], ["Ended", formatTime(cluster.ended_at)]]} /></section></div>;
}

function Steps({cluster, selected, onSelect}: {cluster: EmrCluster; selected: string | null; onSelect: (step: EmrStep) => void}) {
  const [query, setQuery] = useState("");
  const steps = cluster.steps.filter(step => `${step.name} ${step.id} ${step.state} ${step.args.join(" ")}`.toLowerCase().includes(query.toLowerCase()));
  return <div><div className="mb-4 max-w-md"><Input label="Filter Steps" type="search" value={query} onChange={event => setQuery(event.target.value)} /></div><TableFrame><Table><TableHead><TableRow><TableHeaderCell>Name</TableHeaderCell><TableHeaderCell>Command</TableHeaderCell><TableHeaderCell>State</TableHeaderCell><TableHeaderCell>Created</TableHeaderCell><TableHeaderCell>Duration</TableHeaderCell><TableHeaderCell>Action</TableHeaderCell></TableRow></TableHead><TableBody>{steps.length ? steps.map(value => <TableRow key={value.id} role="row" aria-label={`Step ${value.name}`} tabIndex={0} className={`cursor-pointer hover:bg-surface-muted ${selected === value.id ? "bg-brand/8" : ""}`} onClick={() => onSelect(value)} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") onSelect(value); }}><TableCell><strong className="block">{value.name}</strong><small className="font-mono text-ink-muted">{value.id}</small></TableCell><TableCell className="max-w-xs truncate font-mono text-xs" title={value.args.join(" ")}>{value.args.join(" ") || "Unavailable after recovery"}</TableCell><TableCell><StateBadge state={value.state} /></TableCell><TableCell>{formatTime(value.created_at)}</TableCell><TableCell>{duration(value.started_at, value.ended_at)}</TableCell><TableCell>{ACTIVE_STEPS.has(value.state) ? "Cancel / logs" : "View logs"}</TableCell></TableRow>) : <TableRow><TableCell colSpan={6} className="p-6 text-center text-ink-muted">{cluster.steps.length ? "No matching Steps" : "No Steps submitted"}</TableCell></TableRow>}</TableBody></Table></TableFrame></div>;
}

function Diagnostics({api}: {api: EmrUiApi}) {
  const [kind, setKind] = useState<"threads" | "tasks">("threads");
  const [value, setValue] = useState<unknown>(null);
  const [error, setError] = useState<Error | null>(null);
  useEffect(() => { setValue(null); setError(null); void api.diagnostics(kind).then(setValue).catch(caught => setError(asError(caught))); }, [api, kind]);
  return <div><div className="mb-3 flex gap-2"><Button variant={kind === "threads" ? "primary" : "secondary"} onClick={() => setKind("threads")}>Thread stacks</Button><Button variant={kind === "tasks" ? "primary" : "secondary"} onClick={() => setKind("tasks")}>Asyncio tasks</Button></div>{error ? <Alert>{error.message}</Alert> : value ? <JsonView value={value} id={kind} /> : <LoadingState label={`Loading ${kind}`} />}</div>;
}

function StateBadge({state}: {state: string}) {
  const tone = ["WAITING", "RUNNING", "COMPLETED"].includes(state) ? "positive" : ["FAILED", "CANCELLED", "INTERRUPTED", "TERMINATED_WITH_ERRORS"].includes(state) ? "danger" : "warning";
  return <Badge tone={tone}>{state}</Badge>;
}

function formatTime(value: string | null): string { if (!value) return "—"; const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleString(); }
function duration(start: string | null, end: string | null): string { if (!start) return "—"; const milliseconds = (end ? new Date(end) : new Date()).valueOf() - new Date(start).valueOf(); if (!Number.isFinite(milliseconds) || milliseconds < 0) return "—"; const seconds = Math.round(milliseconds / 1000); return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`; }
function asError(value: unknown): Error { return value instanceof Error ? value : new Error(String(value)); }
function displayError(value: Error | null): string { return value instanceof ApiError ? value.display() : value?.message || "Unknown error"; }
