# Organigramm

Das Organigramm stellt die Mitarbeiterhierarchie deines Unternehmens als aufklappbaren Baum dar. Jeder Mitarbeiter wird als Karte angezeigt und unter seiner Führungskraft eingehängt, sodass du auf einen Blick erkennst, wer an wen berichtet. Der Baum wird vollständig aus den bereits synchronisierten Personio-Daten aufgebaut.

## Aufruf

Das Organigramm erreichst du über die Kachel **HR-Dashboard** im Launcher. Sie öffnet den HR-Bereich; wähle dort die Kachel **Organigramm** (Route `/hr/organigramm`). Über der Baumdarstellung zeigt eine Zeile die Anzahl der aktiven Mitarbeiter an (z. B. „48 aktive Mitarbeiter").

## Den Baum lesen und bedienen

- **Wurzeln** — Ganz oben stehen die Mitarbeiter ohne bekannte Führungskraft, also ohne hinterlegten Vorgesetzten in Personio. Sie bilden die Ausgangspunkte des Baums. (Auch Mitarbeiter, deren Vorgesetzter nicht im aktiven Datensatz enthalten ist, werden als Wurzel behandelt.)
- **Auf- und Zuklappen** — Hat ein Mitarbeiter unterstellte Personen, erscheint links neben der Karte ein Pfeil. Klicke darauf, um den Zweig zu öffnen (Pfeil nach unten) oder zu schließen (Pfeil nach rechts). Beim Öffnen der Seite sind alle Zweige zunächst ausgeklappt.
- **Karteninhalt** — Jede Karte zeigt den vollständigen **Namen**, darunter — sofern in Personio hinterlegt — die **Position** und die **Abteilung**. Fehlt der Name, wird ersatzweise die Mitarbeiter-ID angezeigt.
- **Sortierung** — Mitarbeiter auf derselben Ebene sind alphabetisch nach Namen sortiert.

Die Führungsbeziehung stammt aus dem in Personio gepflegten Vorgesetzten-Feld jedes Mitarbeiters.

## Datenquelle

Das Organigramm liest ausschließlich die bereits synchronisierten Personio-Mitarbeiterdaten aus der Datenbank — es findet kein Live-Aufruf bei Personio statt. Angezeigt werden nur **aktive** Mitarbeiter. Ändert sich die Organisation in Personio, erscheinen die Änderungen erst nach der nächsten Synchronisation.

Wird kein Baum angezeigt oder wirkt die Struktur veraltet, ist meist die Personio-Synchronisation die Ursache. Administratoren finden die Einrichtung und Auslösung der Synchronisation im [Personio-Admin-Handbuch](/docs/admin-guide/personio).

## Verwandte Artikel

- [HR-Dashboard](/docs/user-guide/hr-dashboard) — Personalwirtschafts-KPIs aus Personio.
