/** Browser deep-link contract: https://developer.mozilla.org/en-US/docs/Web/API/History_API */
import {describe, expect, it} from "vitest";
import {formatGlueRoute, parseGlueRoute} from "./routes";

describe("Glue history routes", () => {
  it("round-trips database, table, and partition-tab selection", () => {
    const route = {databaseName: "analytics/dev", tableName: "events 2026", tab: "partitions"} as const;
    expect(formatGlueRoute(route)).toBe("/databases/analytics%2Fdev/tables/events%202026/partitions");
    expect(parseGlueRoute(["databases", "analytics/dev", "tables", "events 2026", "partitions"])).toEqual(route);
  });
});
