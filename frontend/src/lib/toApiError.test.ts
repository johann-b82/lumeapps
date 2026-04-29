// Phase 71 Plan 01 (FE-04, D-03): unit tests for toApiError() — the central
// helper that normalizes errors thrown at adapter call sites in
// frontend/src/signage/lib/signageApi.ts into the ApiErrorWithBody contract
// that consumers (PlaylistDeleteDialog, DeviceEditDialog, etc.) pattern-match
// on.
//
// Pitfalls covered:
//   - Pitfall 1 (71-RESEARCH.md): Directus SDK throws PLAIN OBJECTS, not class
//     instances. Tests assert structural shape detection only.
//   - Pitfall 2: ApiErrorWithBody is exported from signage/lib/signageApi.ts
//     (NOT lib/apiClient.ts). Imports below mirror that.
import { describe, it, expect } from "vitest";
import { toApiError } from "./toApiError";
import { ApiErrorWithBody } from "@/signage/lib/signageApi";

describe("toApiError", () => {
  it("Test 1: ApiErrorWithBody passed in returns the SAME instance (identity check)", () => {
    const original = new ApiErrorWithBody(
      404,
      { detail: "not found" },
      "not found",
    );
    const result = toApiError(original);
    expect(result).toBe(original);
  });

  it("Test 2: Directus plain-object error normalizes status, detail, code", () => {
    const directusErr = {
      errors: [{ message: "X", extensions: { code: "FORBIDDEN" } }],
      response: { status: 403 },
    };
    const result = toApiError(directusErr);
    expect(result).toBeInstanceOf(ApiErrorWithBody);
    expect(result.status).toBe(403);
    expect((result.body as { detail?: string }).detail).toBe("X");
    expect((result.body as { code?: string }).code).toBe("FORBIDDEN");
  });

  it("Test 3: Directus plain object with no response.status defaults to status=500", () => {
    const directusErr = {
      errors: [{ message: "boom", extensions: { code: "INTERNAL" } }],
    };
    const result = toApiError(directusErr);
    expect(result).toBeInstanceOf(ApiErrorWithBody);
    expect(result.status).toBe(500);
    expect((result.body as { detail?: string }).detail).toBe("boom");
  });

  it("Test 4: Directus plain object without extensions.code omits code from body but still has detail", () => {
    const directusErr = {
      errors: [{ message: "no code here" }],
      response: { status: 422 },
    };
    const result = toApiError(directusErr);
    expect(result).toBeInstanceOf(ApiErrorWithBody);
    expect(result.status).toBe(422);
    const body = result.body as { detail?: string; code?: string };
    expect(body.detail).toBe("no code here");
    expect(body.code).toBeUndefined();
  });

  it("Test 5: Native Error returns ApiErrorWithBody with status=500 + body.detail", () => {
    const result = toApiError(new Error("boom"));
    expect(result).toBeInstanceOf(ApiErrorWithBody);
    expect(result.status).toBe(500);
    expect((result.body as { detail?: string }).detail).toBe("boom");
    expect(result.message).toBe("boom");
  });

  it("Test 6: Plain string returns ApiErrorWithBody with status=500 + body.detail=string", () => {
    const result = toApiError("x");
    expect(result).toBeInstanceOf(ApiErrorWithBody);
    expect(result.status).toBe(500);
    expect((result.body as { detail?: string }).detail).toBe("x");
  });

  it("Test 7: Directus errors[0].message missing falls back to 'Directus error (CODE)' or 'Directus error'", () => {
    // With code → "Directus error (CODE)"
    const withCode = toApiError({
      errors: [{ extensions: { code: "FAIL" } }],
      response: { status: 500 },
    });
    expect((withCode.body as { detail?: string }).detail).toBe(
      "Directus error (FAIL)",
    );

    // Without code → "Directus error"
    const noCode = toApiError({
      errors: [{}],
      response: { status: 500 },
    });
    expect((noCode.body as { detail?: string }).detail).toBe("Directus error");
  });
});
