/** EMR console route grammar; resource identifiers are opaque URL segments. */
import {encodePathSegment} from "@mystack/ui";

export type EmrTab = "overview" | "steps" | "logs" | "diagnostics" | "raw";
export type EmrRoute = {clusterId: string | null; stepId: string | null; tab: EmrTab};

export function parseEmrRoute(segments: string[]): EmrRoute {
  if (segments[0] !== "clusters" || !segments[1]) return rootEmrRoute();
  const clusterId = segments[1];
  if (segments[2] === "steps") {
    return segments[3]
      ? {clusterId, stepId: segments[3], tab: "logs"}
      : {clusterId, stepId: null, tab: "steps"};
  }
  const tab = segments[2];
  if (tab === "logs" || tab === "diagnostics" || tab === "raw") {
    return {clusterId, stepId: null, tab};
  }
  return {clusterId, stepId: null, tab: "overview"};
}

export function formatEmrRoute(route: EmrRoute): string {
  if (!route.clusterId) return "/";
  const cluster = `/clusters/${encodePathSegment(route.clusterId)}`;
  if (route.tab === "overview") return cluster;
  if (route.tab === "steps") return `${cluster}/steps`;
  if (route.tab === "logs" && route.stepId) {
    return `${cluster}/steps/${encodePathSegment(route.stepId)}/logs`;
  }
  return `${cluster}/${route.tab}`;
}

export function rootEmrRoute(): EmrRoute {
  return {clusterId: null, stepId: null, tab: "overview"};
}
