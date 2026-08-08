/** React UI smoke contract: https://react.dev/learn/typescript */
import "@testing-library/jest-dom/vitest";
import {render, screen} from "@testing-library/react";
import {expect, it, vi} from "vitest";
import App from "./App";

vi.mock("./api", () => ({EmrUiApi: class {
  config = async () => ({refresh_interval_seconds: 60, log_stream_poll_interval_seconds: 1, log_stream_timeout_seconds: 30, log_buffer_bytes: 4096});
  resources = async () => ({schema_version: 1, service: "emr", emulator: {mode: "Spark local mode", config_fingerprint: "test", default_release_label: "emr-7.8.0", release_profiles: {"emr-7.8.0": {runtime_profile: "spark", aws_spark_version: "3.5.4"}}, notice: "No EC2"}, compatibility: {classification: "PARTIAL", implemented_operation_count: 20, model_operation_count: 50, implemented_operations: []}, counts: {clusters: 0, steps: 0, recovered_clusters: 0}, resources: {clusters: []}});
}}));

it("renders the service-owned EMR application without an auth control", async () => {
  render(<App />);
  expect(await screen.findByRole("heading", {name: "Clusters", level: 1})).toBeVisible();
  expect(screen.getByRole("button", {name: "Create cluster"})).toBeVisible();
  expect(screen.queryByLabelText(/management token/i)).not.toBeInTheDocument();
});
