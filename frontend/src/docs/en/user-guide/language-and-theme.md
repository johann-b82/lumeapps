# Language & Dark Mode

The KPI Dashboard supports two interface languages (English and German) and both light and dark mode. Both preferences are remembered in your browser so your choices persist across sessions.

## Language Toggle

The language toggle is located in the **top navigation bar** on the right side. It shows the label of the target language — **"DE"** when the interface is in English, **"EN"** when the interface is in German.

Clicking the toggle switches the entire application to the other language immediately. No page reload is required. All labels, headings, and messages update at once.

Your language preference is saved to your browser's `localStorage` and survives page refreshes and browser restarts.

## Dark Mode Toggle

The dark mode toggle is located in the **top navigation bar** on the right side, next to the language toggle.

- In **light mode** the toggle shows a moon icon. Click it to switch to dark mode.
- In **dark mode** the toggle shows a sun icon. Click it to switch back to light mode.

### OS Theme Detection

When you have not yet clicked the dark mode toggle, the dashboard follows your operating system's `prefers-color-scheme` setting automatically. If your OS switches between light and dark (e.g. at sunrise/sunset), the dashboard follows along.

Once you click the toggle for the first time, your explicit preference is saved to `localStorage` and the OS setting no longer overrides it.

> **Tip:** If you want to go back to following your operating system's theme, clear your browser's local storage for this site.

## Related Articles

- [Introduction](intro)
