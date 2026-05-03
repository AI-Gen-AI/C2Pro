import { healthHandler } from "./custom/health";
import { demoDataHandlers } from "./custom/demo-data";
import { processingStreamHandler } from "./custom/processing-stream";
import { uploadHandlers } from "./custom/uploads";
import { alertReviewHandlers } from "./custom/alert-review";
import { legalDisclaimerHandlers } from "./custom/legal-disclaimer";
import { cookieConsentHandlers } from "./custom/cookie-consent";
import { onboardingSampleProjectHandlers } from "./custom/onboarding-sample-project";
import { s312A11yResponsiveHandlers } from "./custom/s3-12-a11y-responsive";
import { documentViewerHandlers } from "./custom/document-viewer";
import { observabilityHandlers } from "./custom/observability";
import { raciHandlers } from "./custom/raci";
import { aiAnalyticsHandlers } from "./custom/ai-analytics";

export const browserHandlers = [
  healthHandler,
  processingStreamHandler,
  ...demoDataHandlers,
  ...alertReviewHandlers,
  ...legalDisclaimerHandlers,
  ...cookieConsentHandlers,
  ...s312A11yResponsiveHandlers,
  ...observabilityHandlers,
  ...raciHandlers,
  ...aiAnalyticsHandlers,
];

export const testHandlers = [
  ...browserHandlers,
  ...uploadHandlers,
  ...onboardingSampleProjectHandlers,
  ...documentViewerHandlers,
];
