/** Service-owned Glue Catalog explorer assembled only from shared @mystack/ui primitives. */
import {Alert, ApiError, AppShell, Badge, Button, DefinitionGrid, EmptyState, Input, JsonView, LoadingState, Panel, PanelHeader, SummaryCard, Table, TableBody, TableCell, TableFrame, TableHead, TableHeaderCell, TableRow, Tabs, useBrowserRoute, usePollingResource} from "@mystack/ui";
import {useCallback, useEffect, useState} from "react";
import {GlueUiApi} from "./api";
import {formatGlueRoute, parseGlueRoute, rootGlueRoute, type GlueTab} from "./routes";
import type {GlueDatabase, GlueResourceDocument, GlueTable} from "./types";

const api = new GlueUiApi();

export default function App() {
  const [interval, setIntervalSeconds] = useState(2);
  const {route, navigate} = useBrowserRoute("/_mystack/ui/glue", parseGlueRoute, formatGlueRoute);
  const load = useCallback(() => api.resources(), []);
  const resource = usePollingResource<GlueResourceDocument>(load, interval * 1000);
  useEffect(() => { void api.config().then(value => setIntervalSeconds(value.refresh_interval_seconds)); }, []);
  const databases = resource.data?.resources.databases || [];
  useEffect(() => {
    if (!resource.data) return;
    const selectedDatabase = databases.find(value => value.name === route.databaseName);
    if (route.databaseName && !selectedDatabase) {
      navigate(rootGlueRoute(), true);
    } else if (route.tableName && selectedDatabase && !selectedDatabase.tables.some(value => value.name === route.tableName)) {
      navigate({databaseName: selectedDatabase.name, tableName: null, tab: "schema"}, true);
    }
  }, [databases, navigate, resource.data, route.databaseName, route.tableName]);
  const database = databases.find(value => value.name === route.databaseName) || null;
  const table = database?.tables.find(value => value.name === route.tableName) || null;
  const status = resource.error ? "Attention required" : resource.busy ? "Refreshing…" : resource.updatedAt ? `Updated ${resource.updatedAt.toLocaleTimeString()}` : "Starting…";
  return <AppShell service="AWS Glue Data Catalog" homeHref="/_mystack/ui/glue/" title="Data Catalog" description="Explore databases, tables, Glue type strings, partition keys, storage metadata, and partitions used by Spark, Hive, Iceberg, boto3, and AWS SDK for pandas." status={status} navigation={<><a className="rounded-control px-3 py-1.5 text-sm text-code-ink/75 hover:bg-white/10 hover:text-white" href="/_mystack/ui/emr/">EMR</a><a aria-current="page" className="rounded-control bg-white/12 px-3 py-1.5 text-sm font-bold text-white" href="/_mystack/ui/glue/">Glue</a></>} actions={<Button onClick={() => void resource.refresh()} disabled={resource.busy}>Refresh</Button>}>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><SummaryCard label="Mode" value={resource.data?.emulator.mode || "Glue Data Catalog"} /><SummaryCard label="Runtime" value={resource.data?.emulator.runtime_profile || "—"} /><SummaryCard label="Databases" value={resource.data?.counts.databases ?? "—"} /><SummaryCard label="Tables / partitions" value={resource.data ? `${resource.data.counts.tables} / ${resource.data.counts.partitions}` : "—"} /></div>
    {resource.data?.emulator.notice && <p className="mt-3 text-sm text-ink-muted">{resource.data.emulator.notice}</p>}
    {resource.error && <div className="mt-4"><Alert>{displayError(resource.error)}</Alert></div>}
    {!resource.data ? <LoadingState label="Loading Glue Data Catalog" /> : <div className="mt-5 grid min-w-0 gap-5 xl:grid-cols-[18rem_18rem_minmax(0,1fr)]">
      <DatabaseList values={databases} selected={route.databaseName} onSelect={name => navigate({databaseName: name, tableName: null, tab: "schema"})} />
      <TableList database={database} selected={route.tableName} onSelect={name => navigate({databaseName: database?.name || null, tableName: name, tab: "schema"})} />
      <Panel className="min-w-0 overflow-hidden">{!table || !database ? <EmptyState title="Explore the Data Catalog" description="Select a database and table to inspect its schema, partitions, storage, parameters, and diagnostics." /> : <TableDetail api={api} database={database} table={table} activeTab={route.tab} onTab={tab => navigate({databaseName: database.name, tableName: table.name, tab})} />}</Panel>
    </div>}
  </AppShell>;
}

function DatabaseList({values, selected, onSelect}: {values: GlueDatabase[]; selected: string | null; onSelect: (name: string) => void}) {
  const [query, setQuery] = useState("");
  const filtered = values.filter(value => `${value.name} ${value.description || ""} ${value.location_uri || ""}`.toLowerCase().includes(query.toLowerCase()));
  return <Panel className="overflow-hidden"><PanelHeader eyebrow="Catalog" title="Databases" actions={<Badge>{values.length}</Badge>} /><div className="p-4"><Input label="Filter databases" type="search" value={query} onChange={event => setQuery(event.target.value)} /><div className="mt-3 grid gap-2" role="list">{filtered.length ? filtered.map(value => <ResourceButton key={value.name} label={`Database ${value.name}`} title={value.name} subtitle={`${value.tables.length} tables`} selected={selected === value.name} onClick={() => onSelect(value.name)} />) : <p className="p-4 text-center text-sm text-ink-muted">{values.length ? "No matching databases" : "No databases"}</p>}</div></div></Panel>;
}

function TableList({database, selected, onSelect}: {database: GlueDatabase | null; selected: string | null; onSelect: (name: string) => void}) {
  const [query, setQuery] = useState("");
  const values = (database?.tables || []).filter(value => `${value.name} ${value.table_type || ""} ${value.location || ""}`.toLowerCase().includes(query.toLowerCase()));
  return <Panel className="overflow-hidden"><PanelHeader eyebrow={database?.name || "Select database"} title="Tables" actions={<Badge>{database?.tables.length || 0}</Badge>} /><div className="p-4"><Input label="Filter tables" type="search" value={query} onChange={event => setQuery(event.target.value)} /><div className="mt-3 grid gap-2" role="list">{!database ? <p className="p-4 text-center text-sm text-ink-muted">Select a database</p> : values.length ? values.map(value => <ResourceButton key={value.id} label={`Table ${value.name}`} title={value.name} subtitle={`${value.table_type || "TABLE"} · ${value.columns.length} columns`} selected={selected === value.name} onClick={() => onSelect(value.name)} />) : <p className="p-4 text-center text-sm text-ink-muted">{database.tables.length ? "No matching tables" : "No tables"}</p>}</div></div></Panel>;
}

function ResourceButton({label, title, subtitle, selected, onClick}: {label: string; title: string; subtitle: string; selected: boolean; onClick: () => void}) {
  return <button type="button" aria-label={label} aria-current={selected ? "true" : undefined} onClick={onClick} className={`min-w-0 rounded-control border p-3 text-left ${selected ? "border-brand bg-brand/8" : "border-border hover:bg-surface-muted"}`}><strong className="block truncate text-sm">{title}</strong><small className="block truncate text-xs text-ink-muted">{subtitle}</small></button>;
}

function TableDetail({api, database, table, activeTab, onTab}: {api: GlueUiApi; database: GlueDatabase; table: GlueTable; activeTab: GlueTab; onTab: (id: GlueTab) => void}) {
  return <><PanelHeader eyebrow={database.name} title={table.name} actions={<Badge tone="info">{table.table_type || "TABLE"}</Badge>} /><div className="p-5"><p className="mb-4 break-all font-mono text-xs text-ink-muted">{table.id}</p><DefinitionGrid items={[["Location", table.location || "Not configured"], ["Version", table.version_id], ["Columns", table.columns.length], ["Partitions", table.partitions.length], ["Archived versions", table.archived_version_count], ["Created", formatTime(table.created_at)], ["Updated", formatTime(table.updated_at)], ["Classification", table.parameters.classification || "—"]]} /></div><Tabs label="Table detail views" active={activeTab} onChange={value => onTab(value as GlueTab)} tabs={[
    {id: "schema", label: "Schema", panel: <Schema table={table} />},
    {id: "partitions", label: "Partitions", panel: <Partitions table={table} />},
    {id: "parameters", label: "Parameters", panel: <JsonView value={table.parameters} id="parameterList" />},
    {id: "diagnostics", label: "Diagnostics", panel: <Diagnostics api={api} />},
    {id: "raw", label: "Raw detail", panel: <JsonView value={{database: {name: database.name, description: database.description, location_uri: database.location_uri, parameters: database.parameters}, table}} id="glueRaw" />},
  ]} /></>;
}

function Schema({table}: {table: GlueTable}) {
  return <div className="grid gap-6"><section><h3 className="mb-2 font-bold">Columns</h3><TableFrame><Table><TableHead><TableRow><TableHeaderCell>#</TableHeaderCell><TableHeaderCell>Name</TableHeaderCell><TableHeaderCell>Type</TableHeaderCell><TableHeaderCell>Comment</TableHeaderCell></TableRow></TableHead><TableBody id="columnRows">{table.columns.length ? table.columns.map((column, index) => <TableRow key={`${column.Name}-${index}`}><TableCell>{index + 1}</TableCell><TableCell className="font-bold">{column.Name || ""}</TableCell><TableCell className="font-mono text-xs">{column.Type || ""}</TableCell><TableCell>{column.Comment || "—"}</TableCell></TableRow>) : <TableRow><TableCell colSpan={4} className="p-4 text-center text-ink-muted">No columns</TableCell></TableRow>}</TableBody></Table></TableFrame></section><section><h3 className="mb-2 font-bold">Partition keys</h3><div id="partitionKeyList" className="flex flex-wrap gap-2">{table.partition_keys.length ? table.partition_keys.map(key => <Badge key={key.Name}><b>{key.Name}</b>&nbsp;· {key.Type}</Badge>) : <p className="text-sm text-ink-muted">This table is not partitioned.</p>}</div></section></div>;
}

function Partitions({table}: {table: GlueTable}) {
  const [query, setQuery] = useState("");
  const partitions = table.partitions.filter(value => JSON.stringify(value.values).toLowerCase().includes(query.toLowerCase()));
  return <div><div className="mb-4 max-w-md"><Input label="Filter partitions" type="search" value={query} onChange={event => setQuery(event.target.value)} /></div><TableFrame><Table><TableHead><TableRow>{table.partition_keys.length ? table.partition_keys.map(key => <TableHeaderCell key={key.Name}>{key.Name || "Value"}</TableHeaderCell>) : <TableHeaderCell>Values</TableHeaderCell>}<TableHeaderCell>Location</TableHeaderCell><TableHeaderCell>Updated</TableHeaderCell></TableRow></TableHead><TableBody id="partitionRows">{partitions.length ? partitions.map(value => <TableRow key={value.id}>{table.partition_keys.length ? table.partition_keys.map((key, index) => <TableCell key={`${value.id}-${key.Name}`} className="font-mono text-xs">{value.values[index] ?? "—"}</TableCell>) : <TableCell className="font-mono text-xs">{value.values.join("/") || "—"}</TableCell>}<TableCell className="max-w-md break-all font-mono text-xs">{value.definition.StorageDescriptor?.Location || "—"}</TableCell><TableCell>{formatTime(value.updated_at)}</TableCell></TableRow>) : <TableRow><TableCell colSpan={Math.max(table.partition_keys.length, 1) + 2} className="p-5 text-center text-ink-muted">{table.partitions.length ? "No matching partitions" : "No partitions"}</TableCell></TableRow>}</TableBody></Table></TableFrame></div>;
}

function Diagnostics({api}: {api: GlueUiApi}) {
  const [kind, setKind] = useState<"threads" | "tasks">("threads");
  const [value, setValue] = useState<unknown>(null);
  const [error, setError] = useState<Error | null>(null);
  useEffect(() => { setValue(null); setError(null); void api.diagnostics(kind).then(setValue).catch(caught => setError(asError(caught))); }, [api, kind]);
  return <div><div className="mb-3 flex gap-2"><Button variant={kind === "threads" ? "primary" : "secondary"} onClick={() => setKind("threads")}>Thread stacks</Button><Button variant={kind === "tasks" ? "primary" : "secondary"} onClick={() => setKind("tasks")}>Asyncio tasks</Button></div>{error ? <Alert>{error.message}</Alert> : value ? <JsonView value={value} id={kind} /> : <LoadingState label={`Loading ${kind}`} />}</div>;
}

function formatTime(value: string | null): string { if (!value) return "—"; const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleString(); }
function asError(value: unknown): Error { return value instanceof Error ? value : new Error(String(value)); }
function displayError(value: Error): string { return value instanceof ApiError ? value.display() : value.message; }
