import { describe, expect, it } from "vitest";
import { browserHandlers, testHandlers } from "./index";

function handlerPathIncludes(
  handler: (typeof browserHandlers)[number],
  text: string,
) {
  return String(handler.info.path).includes(text);
}

describe("mock handler boundaries", () => {
  it("keeps synthetic upload handlers out of browser-loaded demo handlers", () => {
    const uploadHandlerPresent = browserHandlers.some((handler) =>
      handlerPathIncludes(handler, "/uploads/"),
    );

    expect(uploadHandlerPresent).toBe(false);
  });

  it("retains synthetic upload handlers for node-based test coverage", () => {
    const uploadHandlerPresent = testHandlers.some((handler) =>
      handlerPathIncludes(handler, "/uploads/"),
    );

    expect(uploadHandlerPresent).toBe(true);
  });

  it("keeps synthetic onboarding sample-project handlers out of browser-loaded demo handlers", () => {
    const onboardingHandlerPresent = browserHandlers.some((handler) =>
      handlerPathIncludes(handler, "/onboarding/sample-project/"),
    );

    expect(onboardingHandlerPresent).toBe(false);
  });

  it("retains synthetic onboarding sample-project handlers for node-based test coverage", () => {
    const onboardingHandlerPresent = testHandlers.some((handler) =>
      handlerPathIncludes(handler, "/onboarding/sample-project/"),
    );

    expect(onboardingHandlerPresent).toBe(true);
  });

  it("keeps synthetic document viewer handlers out of browser-loaded demo handlers", () => {
    const viewerHandlerPresent = browserHandlers.some(
      (handler) =>
        handlerPathIncludes(handler, "/documents/:documentId/download") ||
        handlerPathIncludes(handler, "/documents/:documentId/entities"),
    );

    expect(viewerHandlerPresent).toBe(false);
  });

  it("retains synthetic document viewer handlers for node-based test coverage", () => {
    const viewerHandlerPresent = testHandlers.some(
      (handler) =>
        handlerPathIncludes(handler, "/documents/:documentId/download") ||
        handlerPathIncludes(handler, "/documents/:documentId/entities"),
    );

    expect(viewerHandlerPresent).toBe(true);
  });
});
