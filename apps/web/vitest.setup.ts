import "@testing-library/jest-dom";
import "./src/tests/setup";

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
