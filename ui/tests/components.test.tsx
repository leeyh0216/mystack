/** Shared primitive contracts: https://testing-library.com/docs/react-testing-library/intro/ */
import "@testing-library/jest-dom/vitest";
import {fireEvent, render, screen} from "@testing-library/react";
import {useState} from "react";
import {describe, expect, it} from "vitest";
import {Input, Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow, Tabs} from "../src";

describe("shared design-system primitives", () => {
  it("associates centrally managed input labels and hints", () => {
    render(<Input label="Cluster name" hint="Required by RunJobFlow" />);
    expect(screen.getByLabelText("Cluster name")).toHaveAccessibleDescription("Required by RunJobFlow");
  });

  it("implements keyboard tab navigation", () => {
    function Harness() {
      const [active, setActive] = useState("one");
      return <Tabs label="Details" active={active} onChange={setActive} tabs={definitions} />;
    }
    render(<Harness />);
    fireEvent.keyDown(screen.getByRole("tab", {name: "One"}), {key: "ArrowRight"});
    expect(screen.getByRole("tab", {name: "Two"})).toHaveFocus();
  });

  it("provides the service-neutral table structure", () => {
    render(<Table><TableHead><TableRow><TableHeaderCell>Name</TableHeaderCell></TableRow></TableHead><TableBody><TableRow><TableCell>example</TableCell></TableRow></TableBody></Table>);
    expect(screen.getByRole("columnheader", {name: "Name"})).toBeVisible();
    expect(screen.getByRole("cell", {name: "example"})).toBeVisible();
  });
});

const definitions = [
  {id: "one", label: "One", panel: <p>First</p>},
  {id: "two", label: "Two", panel: <p>Second</p>},
];
