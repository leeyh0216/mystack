/** Polling effect lifecycle: https://react.dev/learn/synchronizing-with-effects */
import {render} from "@testing-library/react";
import {usePollingResource} from "@mystack/ui";
import {useEffect} from "react";
import {afterEach, describe, expect, it, vi} from "vitest";

function PollingProbe({load}: {load: () => Promise<string>}) {
  const resource = usePollingResource(load, 50);
  return <output>{resource.data ?? "loading"}</output>;
}

let setupBoundaryUnmounts = 0;

function SetupBoundaryProbe() {
  const resource = usePollingResource(async () => "ready", 50);
  useEffect(() => () => {
    setupBoundaryUnmounts += 1;
  }, []);
  return <output data-testid="setup-boundary-probe">{resource.data ?? "loading"}</output>;
}

afterEach(() => {
  vi.useRealTimers();
});

it("cleans a polling timer when the rendered tree is unmounted", async () => {
  vi.useFakeTimers();
  const load = vi.fn(async () => "ready");
  const clearInterval = vi.spyOn(window, "clearInterval");
  const view = render(<PollingProbe load={load} />);

  view.unmount();
  expect(clearInterval).toHaveBeenCalled();
  await vi.advanceTimersByTimeAsync(50);
  expect(load).toHaveBeenCalledTimes(1);
});

describe.sequential("shared setup boundary", () => {
  it("leaves a rendered polling tree for the shared setup to unmount", () => {
    setupBoundaryUnmounts = 0;
    render(<SetupBoundaryProbe />);
    expect(setupBoundaryUnmounts).toBe(0);
  });

  it("unmounts the preceding tree after its test boundary", () => {
    expect(setupBoundaryUnmounts).toBe(1);
    expect(document.querySelector("[data-testid='setup-boundary-probe']")).toBeNull();
  });
});
