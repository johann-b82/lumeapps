/**
 * EmbedJoinersPage — kiosk-friendly /embed/joiners. Sibling of
 * EmbedBirthdaysPage; renders just JoinersCard with no admin shell.
 */
import { JoinersCard } from "@/components/dashboard/JoinersCard";

export function EmbedJoinersPage() {
  return (
    <div className="min-h-screen w-screen bg-background p-6">
      <JoinersCard embed />
    </div>
  );
}
