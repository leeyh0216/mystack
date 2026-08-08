/** Glue explorer route grammar; database/table names remain opaque URL segments. */
import {encodePathSegment} from "@mystack/ui";

export type GlueTab = "schema" | "partitions" | "parameters" | "diagnostics" | "raw";
export type GlueRoute = {databaseName: string | null; tableName: string | null; tab: GlueTab};

export function parseGlueRoute(segments: string[]): GlueRoute {
  if (segments[0] !== "databases" || !segments[1]) return rootGlueRoute();
  const databaseName = segments[1];
  if (segments[2] !== "tables" || !segments[3]) {
    return {databaseName, tableName: null, tab: "schema"};
  }
  const candidate = segments[4];
  const tab: GlueTab = candidate === "partitions" || candidate === "parameters" || candidate === "diagnostics" || candidate === "raw" ? candidate : "schema";
  return {databaseName, tableName: segments[3], tab};
}

export function formatGlueRoute(route: GlueRoute): string {
  if (!route.databaseName) return "/";
  const database = `/databases/${encodePathSegment(route.databaseName)}`;
  if (!route.tableName) return database;
  const table = `${database}/tables/${encodePathSegment(route.tableName)}`;
  return route.tab === "schema" ? table : `${table}/${route.tab}`;
}

export function rootGlueRoute(): GlueRoute {
  return {databaseName: null, tableName: null, tab: "schema"};
}
