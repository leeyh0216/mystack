/** Service-relative read adapter; official catalog API: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html */
import {requestJson} from "@mystack/ui";
import type {GlueResourceDocument, UiConfig} from "./types";

const UI_BASE = "/_mystack/ui/glue/";

export class GlueUiApi {
  resources(): Promise<GlueResourceDocument> { return requestJson("resources", UI_BASE); }
  config(): Promise<UiConfig> { return requestJson("config", UI_BASE); }
  diagnostics(kind: "threads" | "tasks"): Promise<unknown> { return requestJson(`diagnostics/${kind}`, UI_BASE); }
}
