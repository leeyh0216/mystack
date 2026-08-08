/** Static dependency and theme ownership contracts for the shared UI boundary. */
import {readFileSync} from "node:fs";
import {describe, expect, it} from "vitest";

const read = (path: string) => readFileSync(path, "utf8");

describe("frontend architecture", () => {
  it("keeps all semantic theme tokens in the shared design set", () => {
    const theme = read("ui/src/theme.css");
    expect(theme).toContain('[data-theme="mystack-light"]');
    expect(theme).toContain('[data-theme="mystack-midnight"]');
    for (const serviceSource of [read("emr/ui/src/App.tsx"), read("glue/ui/src/App.tsx")]) {
      expect(serviceSource).not.toMatch(/--mystack-[a-z-]+/);
    }
  });

  it("keeps shared UI independent of both service applications", () => {
    const sharedSources = ["components.tsx", "hooks.ts", "http.ts", "routes.ts", "index.ts"]
      .map(name => read(`ui/src/${name}`))
      .join("\n");
    expect(sharedSources).not.toMatch(/from\s+["'][^"']*(?:emr|glue)\/ui/);
    expect(read("emr/ui/src/App.tsx")).toContain('from "@mystack/ui"');
    expect(read("glue/ui/src/App.tsx")).toContain('from "@mystack/ui"');
  });
});
