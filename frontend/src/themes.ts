/** Accent themes unlocked by level — levels finally pay out something visible.
 *
 * Unlock state derives from the server-side level (XP is earned, never bought);
 * only the *chosen* theme lives in localStorage. A theme is a data-theme
 * attribute on <html>; the palettes are defined in index.css.
 */

export interface Theme {
  id: string;
  name: string;
  swatch: string; // the accent color, shown on the picker button
  unlockLevel: number;
}

export const THEMES: Theme[] = [
  { id: "default", name: "Circuit Blue", swatch: "#5b8cff", unlockLevel: 0 },
  { id: "forest", name: "Forest", swatch: "#34d399", unlockLevel: 2 },
  { id: "ember", name: "Ember", swatch: "#fb7185", unlockLevel: 4 },
  { id: "violet", name: "Violet Storm", swatch: "#a78bfa", unlockLevel: 6 },
  { id: "gold", name: "Gold Rush", swatch: "#fbbf24", unlockLevel: 9 },
  { id: "cyber", name: "Cyberdeck", swatch: "#22d3ee", unlockLevel: 12 },
];

const KEY = "studyengine.theme";

export function currentTheme(): string {
  return localStorage.getItem(KEY) ?? "default";
}

export function applyTheme(id: string): void {
  localStorage.setItem(KEY, id);
  document.documentElement.setAttribute("data-theme", id);
}

/** Set the stored theme on load; falls back to default for unknown ids. */
export function initTheme(): void {
  const id = currentTheme();
  const known = THEMES.some((t) => t.id === id);
  document.documentElement.setAttribute("data-theme", known ? id : "default");
}

/** Themes whose unlock sits exactly at `level` — for the level-up toast. */
export function unlockedAt(level: number): Theme[] {
  return THEMES.filter((t) => t.unlockLevel === level && level > 0);
}
