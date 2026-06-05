/**
 * EmbedBirthdaysPage — kiosk-friendly /embed/birthdays.
 *
 * Strips the full admin shell (no NavBar, no SubHeader, no AuthGate) and
 * just renders BirthdaysCard against the unauthenticated /api/hr/embed
 * endpoints. Designed to be iframed from a signage URL playlist item.
 * Black background to blend into the kiosk's default canvas.
 */
import { BirthdaysCard } from "@/components/dashboard/BirthdaysCard";

export function EmbedBirthdaysPage() {
  return (
    <div className="min-h-screen w-screen bg-background p-6">
      <BirthdaysCard embed />
    </div>
  );
}
