# Sprache & Dunkelmodus

Das KPI Dashboard unterstützt zwei Sprachen (Deutsch und Englisch) sowie einen hellen und einen dunklen Modus. Beide Einstellungen werden in deinem Browser gespeichert und bleiben auch nach einem Neustart erhalten.

## Sprachumschalter

Der Sprachumschalter befindet sich in der **oberen Navigationsleiste** auf der rechten Seite. Er zeigt das Kürzel der Zielsprache — **"EN"** wenn die Oberfläche auf Deutsch eingestellt ist, **"DE"** wenn sie auf Englisch ist.

Ein Klick auf den Umschalter wechselt sofort die gesamte Anwendung in die andere Sprache. Es ist kein Neuladen der Seite erforderlich. Alle Beschriftungen, Überschriften und Meldungen werden auf einmal aktualisiert.

Deine Spracheinstellung wird im `localStorage` deines Browsers gespeichert und bleibt nach Seitenaktualisierungen und Browser-Neustarts erhalten.

## Dunkelmodus-Umschalter

Der Dunkelmodus-Umschalter befindet sich in der **oberen Navigationsleiste** auf der rechten Seite, neben dem Sprachumschalter.

- Im **hellen Modus** zeigt der Umschalter ein Mond-Symbol. Klicke darauf, um in den dunklen Modus zu wechseln.
- Im **dunklen Modus** zeigt der Umschalter ein Sonnen-Symbol. Klicke darauf, um zum hellen Modus zurückzukehren.

### Systemdesign-Erkennung

Wenn du den Dunkelmodus-Umschalter noch nicht geklickt hast, folgt das Dashboard automatisch der `prefers-color-scheme`-Einstellung deines Betriebssystems. Wechselt dein Betriebssystem zwischen hell und dunkel (z. B. bei Sonnenauf- und -untergang), zieht das Dashboard nach.

Sobald du den Umschalter zum ersten Mal klickst, wird deine explizite Einstellung im `localStorage` gespeichert, und die Betriebssystemeinstellung hat keinen Einfluss mehr.

> **Tipp:** Wenn du möchten, dass das Dashboard wieder dem Systemdesign deines Betriebssystems folgt, lösche den lokalen Speicher (Local Storage) dieser Website in deinem Browser.

## Verwandte Artikel

- [Einleitung](intro)
