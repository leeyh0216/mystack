import {render} from "@testing-library/react";
import {usePollingResource} from "@mystack/ui";
import {expect, it, vi} from "vitest";

function PollingProbe() {
  const resource = usePollingResource(async () => "ready", 50);
  return <output>{resource.data ?? "loading"}</output>;
}

it("cleans a polling timer when the rendered tree is unmounted", () => {
  vi.useFakeTimers();
  const clearInterval = vi.spyOn(window, "clearInterval");
  const view = render(<PollingProbe />);

  view.unmount();
  expect(clearInterval).toHaveBeenCalled();
  vi.useRealTimers();
});
