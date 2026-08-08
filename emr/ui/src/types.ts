/** EMR resource/state references: https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html */
export interface UiConfig {
  refresh_interval_seconds: number;
  log_stream_poll_interval_seconds: number;
  log_stream_timeout_seconds: number;
  log_buffer_bytes: number;
}

export interface EmrResourceDocument {
  schema_version: number;
  service: "emr";
  emulator: {
    mode: string;
    config_fingerprint: string;
    default_release_label: string;
    release_profiles: Record<string, {runtime_profile: string; aws_spark_version: string; submit_aliases: string[]}>;
    notice: string;
  };
  compatibility: {
    classification: string;
    implemented_operation_count: number;
    model_operation_count: number;
    implemented_operations: string[];
  };
  counts: {clusters: number; steps: number; recovered_clusters: number};
  resources: {clusters: EmrCluster[]};
}

export interface EmrCluster {
  id: string;
  arn: string | null;
  name: string;
  state: string;
  state_reason: {code: string; message: string};
  release_label: string;
  log_uri: string | null;
  service_role: string | null;
  step_concurrency_level: number;
  instance_config: Record<string, unknown>;
  created_at: string | null;
  ready_at: string | null;
  ended_at: string | null;
  keep_alive: boolean;
  termination_protected: boolean;
  visible_to_all_users: boolean;
  applications: string[];
  bootstrap_actions: Array<{name: string; path: string; argument_count: number}>;
  tags: Record<string, string>;
  recovered: boolean;
  steps: EmrStep[];
}

export interface EmrStep {
  id: string;
  name: string;
  state: string;
  state_reason: {code: string; message: string};
  action_on_failure: string;
  created_at: string | null;
  started_at: string | null;
  ended_at: string | null;
  recovered: boolean;
  jar: string;
  main_class: string | null;
  args: string[];
  properties: Record<string, string>;
  failure_details: Record<string, string> | null;
}

export interface LogPublication {
  status: string;
  log_uri?: string;
  published_keys?: string[];
  exit_code?: number | null;
  error?: string;
  reason?: string;
}

export interface EmrLogs {
  step_id: string;
  step_name: string;
  step_state: string;
  stdout: string;
  stderr: string;
  log_publication: LogPublication;
  resolved_command: {status: string; arguments: string[]};
}

export interface EmrLogChunk {
  stdout: string;
  stderr: string;
  stdout_next_offset: number;
  stderr_next_offset: number;
  step_state: string;
  complete: boolean;
  log_publication: LogPublication;
}
