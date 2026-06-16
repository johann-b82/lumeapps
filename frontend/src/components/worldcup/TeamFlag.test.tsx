import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TeamFlag } from "./TeamFlag";

describe("TeamFlag", () => {
  it("renders an img when a crest is present", () => {
    const { container } = render(
      <TeamFlag team={{ name: "France", short_name: "FRA", crest: "https://x/fra.png" }} />,
    );
    expect(container.querySelector("img")).not.toBeNull();
  });

  it("renders no img when crest is null", () => {
    const { container } = render(
      <TeamFlag team={{ name: "France", short_name: "FRA", crest: null }} />,
    );
    expect(container.querySelector("img")).toBeNull();
  });
});
