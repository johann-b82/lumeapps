import { useQuery } from "@tanstack/react-query";
import { readMe } from "@directus/sdk";

import { directus } from "@/lib/directusClient";
import { toApiError } from "@/lib/toApiError";

/**
 * Phase 66 D-05: full-field profile fetch for UserMenu + avatar consumers.
 *
 * Second `readMe` call (distinct from the minimal one in AuthContext) so
 * AuthContext stays tight on `id, email, role.name` and the UI layer pulls
 * first_name / last_name / avatar on demand.
 *
 * Field list mirrors the Viewer allowlist on `directus_users` fixed in
 * Phase 65 (AUTHZ-03): id, email, first_name, last_name, avatar, role.
 * `role.name` requires the Viewer read permission on `directus_roles`
 * added in Plan 66-01 Task 1.
 *
 * Invalidated by AuthContext.signOut() via queryClient.clear() (existing).
 */
export interface CurrentUserProfile {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  avatar: string | null;
  role: { name: string } | null;
}

export function useCurrentUserProfile() {
  return useQuery<CurrentUserProfile>({
    queryKey: ["currentUserProfile"],
    queryFn: async () => {
      try {
        const res = await directus.request(
          readMe({
            fields: ["id", "email", "first_name", "last_name", "avatar", "role.name"],
          }),
        );
        return res as CurrentUserProfile;
      } catch (e) { throw toApiError(e); }
    },
  });
}
