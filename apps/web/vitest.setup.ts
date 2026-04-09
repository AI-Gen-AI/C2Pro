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
