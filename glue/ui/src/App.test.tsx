import "@testing-library/jest-dom/vitest";
import {render, screen} from "@testing-library/react";
import {expect, it, vi} from "vitest";
import App from "./App";

vi.mock("./api", () => ({GlueUiApi: class {
  config = async () => ({refresh_interval_seconds: 60});
  resources = async () => ({schema_version: 1, service: "glue", emulator: {mode: "Glue Data Catalog", runtime_profile: "glue-5.0", config_fingerprint: "test", notice: "Jobs are out of scope"}, compatibility: {classification: "PARTIAL", implemented_operation_count: 22, model_operation_count: 50, implemented_operations: []}, counts: {databases: 0, tables: 0, partitions: 0}, resources: {databases: []}});
}}));

it("renders the service-owned Glue explorer without an auth control", async () => {
  render(<App />);
  expect(await screen.findByRole("heading", {name: "Data Catalog", level: 1})).toBeVisible();
  expect(await screen.findByRole("heading", {name: "Databases"})).toBeVisible();
  expect(screen.queryByLabelText(/management token/i)).not.toBeInTheDocument();
});
