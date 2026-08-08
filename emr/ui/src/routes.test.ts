/** Browser deep-link contract: https://developer.mozilla.org/en-US/docs/Web/API/History_API */
import {describe, expect, it} from "vitest";
import {formatEmrRoute, parseEmrRoute} from "./routes";

describe("EMR history routes", () => {
  it("round-trips an opaque cluster and Step log selection", () => {
    const route = {clusterId: "j-A/B", stepId: "s-한글", tab: "logs"} as const;
    expect(formatEmrRoute(route)).toBe("/clusters/j-A%2FB/steps/s-%ED%95%9C%EA%B8%80/logs");
    expect(parseEmrRoute(["clusters", "j-A/B", "steps", "s-한글", "logs"])).toEqual(route);
  });
});
