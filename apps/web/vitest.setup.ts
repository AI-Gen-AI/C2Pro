import {
  ReadableStream,
  TransformStream,
  WritableStream,
} from "node:stream/web";
import "@testing-library/jest-dom/vitest";
import axios from "axios";

process.env.NEXT_PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL || "/api";
axios.defaults.baseURL = "/api";

if (!globalThis.ReadableStream) {
  globalThis.ReadableStream =
    ReadableStream as unknown as typeof globalThis.ReadableStream;
}

if (!globalThis.WritableStream) {
  globalThis.WritableStream =
    WritableStream as unknown as typeof globalThis.WritableStream;
}

if (!globalThis.TransformStream) {
  globalThis.TransformStream =
    TransformStream as unknown as typeof globalThis.TransformStream;
}

// Vitest spawns multiple workers; each worker's setup registers a
// vitest re-executes this setup file per worker/thread on a shared process, so
// register the Vite-CJS-deprecation suppression EXACTLY ONCE. Otherwise the
// process-level "warning" listener (and the console.warn wrapper) accumulate on
// every setup run and trip Node's MaxListenersExceededWarning.
const SUPPRESS_GUARD = Symbol.for("c2pro.vitest.viteCjsWarningSuppressed");
const guardedProcess = process as typeof process & {
  [SUPPRESS_GUARD]?: boolean;
};

if (!guardedProcess[SUPPRESS_GUARD]) {
  guardedProcess[SUPPRESS_GUARD] = true;

  const originalWarn = console.warn.bind(console);
  console.warn = (...args: unknown[]) => {
    if (
      typeof args[0] === "string" &&
      args[0].includes("CJS build of Vite's Node API is deprecated")
    ) {
      return;
    }
    originalWarn(...args);
  };

  process.on("warning", (warning) => {
    if (
      warning.name === "DeprecationWarning" &&
      warning.message.includes("CJS build of Vite's Node API is deprecated")
    ) {
      return;
    }
    console.warn(warning);
  });
}

if (!window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

if (!HTMLElement.prototype.hasPointerCapture) {
  HTMLElement.prototype.hasPointerCapture = () => false;
}
if (!HTMLElement.prototype.setPointerCapture) {
  HTMLElement.prototype.setPointerCapture = () => {};
}
if (!HTMLElement.prototype.releasePointerCapture) {
  HTMLElement.prototype.releasePointerCapture = () => {};
}

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
