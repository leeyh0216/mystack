/** Polling effect lifecycle: https://react.dev/learn/synchronizing-with-effects */
import {render} from "@testing-library/react";
import {usePollingResource} from "@mystack/ui";
import {afterEach, expect, it, vi} from "vitest";

function PollingProbe({load}: {load: () => Promise<string>}) {
  const resource = usePollingResource(load, 50);
  return <output>{resource.data ?? "loading"}</output>;
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
