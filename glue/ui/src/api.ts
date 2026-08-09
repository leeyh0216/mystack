import {requestJson} from "@mystack/ui";
import type {GluePage, GluePartition, GlueTable, GlueUiDocument, UiConfig} from "./types";
const BASE = "/_mystack/ui/glue/";
const path = (value: string) => encodeURIComponent(value);
export class GlueUiApi {
  document(): Promise<GlueUiDocument> { return requestJson("catalog", BASE); }
  databases(cursor?: string): Promise<GluePage> { return requestJson(`catalog/databases${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`, BASE); }
  tables(database: string, cursor?: string): Promise<GluePage<GlueTable>> { return requestJson(`catalog/databases/${path(database)}/tables${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`, BASE); }
  table(database: string, table: string): Promise<{resource: GlueTable; partition_count: number}> { return requestJson(`catalog/databases/${path(database)}/tables/${path(table)}`, BASE); }
  partitions(database: string, table: string, cursor?: string): Promise<GluePage<GluePartition>> { return requestJson(`catalog/databases/${path(database)}/tables/${path(table)}/partitions${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`, BASE); }
  config(): Promise<UiConfig> { return requestJson("config", BASE); }
  diagnostics(kind: "threads" | "tasks"): Promise<unknown> { return requestJson(`diagnostics/${kind}`, BASE); }
}
