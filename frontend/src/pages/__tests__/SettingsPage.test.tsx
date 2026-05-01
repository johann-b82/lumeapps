import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Router } from "wouter";
import { memoryLocation } from "wouter/memory-location";
import { SettingsPage } from "@/pages/SettingsPage";

describe("SettingsPage (redirect)", () => {
  it("renders nothing of its own and redirects to /settings/general", () => {
    const memory = memoryLocation({ path: "/settings", record: true });
    render(
      <Router hook={memory.hook}>
        <SettingsPage />
      </Router>,
    );
    expect(memory.history).toContain("/settings/general");
  });
});
