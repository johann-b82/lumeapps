// Phase 71 Plan 01 (FE-04, D-03/D-03a/D-03b): central helper that normalizes
// any error thrown at adapter call sites in signage/lib/signageApi.ts into
// the ApiErrorWithBody contract that consumers (PlaylistDeleteDialog,
// DeviceEditDialog, etc.) already pattern-match on.
//
// The Directus SDK 21.2.2 throws PLAIN JS OBJECTS, not class instances
// (verified GitHub Issue #23297). Shape:
//   { errors: [{ message, extensions: { code } }], response?: { status } }
// There is no class exported by @directus/sdk for this — do NOT use
// instanceof here (Pitfall 1, 71-RESEARCH.md).
//
// FK 409 ID-reshape is DEFERRED per D-03b — today no Directus-served DELETE
// has FK dependents (all such DELETEs stay on FastAPI). When a Directus
// DELETE with FK dependents lands, extend this helper rather than scattering
// reshape logic across call sites.
import { ApiErrorWithBody } from "@/signage/lib/signageApi";

interface DirectusThrownShape {
  errors?: Array<{
    message?: string;
    extensions?: { code?: string };
  }>;
  response?: { status?: number };
}

/**
 * Normalize any error thrown by an adapter call site into ApiErrorWithBody.
 *
 * Resolution order:
 *   1. Pass-through if already ApiErrorWithBody (avoid double-wrapping).
 *   2. Structural Directus check ("errors" in err) — extract status, detail,
 *      code from the SDK plain-object shape.
 *   3. Native Error → wrap with status=500, detail=err.message.
 *   4. Fallback (string / unknown) → wrap with status=500, detail=String(err).
 */
export function toApiError(err: unknown): ApiErrorWithBody {
  // 1. Pass-through to avoid double-wrapping.
  if (err instanceof ApiErrorWithBody) return err;

  // 2. Directus SDK plain-object shape.
  if (err && typeof err === "object" && "errors" in err) {
    const de = err as DirectusThrownShape;
    const first = de.errors?.[0];
    const status = de.response?.status ?? 500;
    const code = first?.extensions?.code;
    const detail =
      first?.message ?? `Directus error${code ? ` (${code})` : ""}`;
    const body: { detail: string; code?: string } = { detail };
    if (code !== undefined) body.code = code;
    return new ApiErrorWithBody(status, body, detail);
  }

  // 3. Native Error.
  if (err instanceof Error) {
    return new ApiErrorWithBody(500, { detail: err.message }, err.message);
  }

  // 4. Fallback.
  const detail = String(err);
  return new ApiErrorWithBody(500, { detail }, detail);
}
