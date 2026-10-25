/**
 * Vitest global setup — runs before every test file.
 *
 * Imports @testing-library/jest-dom so all its matchers
 * (toBeInTheDocument, toHaveValue, etc.) are available in every test.
 *
 * Also polyfills localStorage for Node.js v22+ where the Web Storage API
 * is partially present but non-functional without a backing store.
 */
import "@testing-library/jest-dom";

// ---------------------------------------------------------------------------
// localStorage polyfill for Node.js v22+ / vitest node-like environments
//
// Node.js 22 introduced localStorage as an undefined global.
// jsdom normally overrides it, but in some vitest configurations the
// Node global wins.  We provide a simple in-memory implementation so
// token storage tests work regardless of which environment runs first.
// ---------------------------------------------------------------------------

if (typeof localStorage === "undefined" || localStorage === null) {
  const store: Record<string, string> = {};
  const localStorageMock: Storage = {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { Object.keys(store).forEach((k) => delete store[k]); },
    key: (index: number) => Object.keys(store)[index] ?? null,
    get length() { return Object.keys(store).length; },
  };
  // Override the non-functional Node.js v22+ global with our mock.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).localStorage = localStorageMock;
}
