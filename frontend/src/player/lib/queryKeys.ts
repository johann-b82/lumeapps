// Phase 47: TanStack Query key factory for the player bundle.
// Mirrors frontend/src/lib/queryKeys.ts factory style; lives in the player tree
// so the admin bundle never imports player keys.

export const playerKeys = {
  all: ["player"] as const,
  playlist: () => [...playerKeys.all, "playlist"] as const,
  pairStatus: (sessionId: string | null) =>
    [...playerKeys.all, "pair-status", sessionId] as const,
};
