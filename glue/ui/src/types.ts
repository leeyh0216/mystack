export interface UiConfig {refresh_interval_seconds: number;}
export interface GlueUiDocument {emulator: {mode: string; runtime_profile: string; notice: string}; compatibility: {classification: string; implemented_operation_count: number};}
export interface GluePage<T = GlueDatabase | GluePartition> {items: T[]; next_cursor: string | null; total_count: number; diagnostics: {query_category: string; query_strategy: string; returned_count: number};}
export interface GlueDatabase {id: string; name: string; description: string | null; location_uri: string | null;}
export interface GlueColumn {Name?: string; Type?: string; Comment?: string;}
export interface GluePartition {id: string; values: string[]; updated_at: string; definition: {StorageDescriptor?: {Location?: string}};}
export interface GlueTable {id: string; name: string; database_name: string; table_type: string | null; location: string | null; columns: GlueColumn[]; partition_keys: GlueColumn[]; parameters: Record<string, string>; version_id: string; archived_version_count: number; created_at: string; updated_at: string; definition: Record<string, unknown>;}
