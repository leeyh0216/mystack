/** Glue catalog structures and types: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html */
export interface UiConfig {refresh_interval_seconds: number;}
export interface GlueResourceDocument {
  schema_version: number;
  service: "glue";
  emulator: {mode: string; runtime_profile: string; config_fingerprint: string; notice: string};
  compatibility: {classification: string; implemented_operation_count: number; model_operation_count: number; implemented_operations: string[]};
  counts: {databases: number; tables: number; partitions: number};
  resources: {databases: GlueDatabase[]};
}
export interface GlueDatabase {
  id: string;
  name: string;
  created_at: string;
  description: string | null;
  location_uri: string | null;
  parameters: Record<string, string>;
  definition: Record<string, unknown>;
  tables: GlueTable[];
}
export interface GlueColumn {Name?: string; Type?: string; Comment?: string;}
export interface GluePartition {
  id: string;
  values: string[];
  created_at: string;
  updated_at: string;
  definition: {StorageDescriptor?: {Location?: string}; [key: string]: unknown};
}
export interface GlueTable {
  id: string;
  name: string;
  database_name: string;
  table_type: string | null;
  location: string | null;
  columns: GlueColumn[];
  partition_keys: GlueColumn[];
  parameters: Record<string, string>;
  version_id: string;
  archived_version_count: number;
  created_at: string;
  updated_at: string;
  definition: Record<string, unknown>;
  partitions: GluePartition[];
}
