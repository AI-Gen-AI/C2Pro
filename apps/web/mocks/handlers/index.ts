import { healthHandler } from "./custom/health";
import { demoDataHandlers } from "./custom/demo-data";
import { processingStreamHandler } from "./custom/processing-stream";
import { uploadHandlers } from "./custom/uploads";
import { alertReviewHandlers } from "./custom/alert-review";
import { legalDisclaimerHandlers } from "./custom/legal-disclaimer";
import { cookieConsentHandlers } from "./custom/cookie-consent";
import { onboardingSampleProjectHandlers } from "./custom/onboarding-sample-project";
import { s312A11yResponsiveHandlers } from "./custom/s3-12-a11y-responsive";

export const handlers = [
  healthHandler,
  processingStreamHandler,
  ...demoDataHandlers,
  ...uploadHandlers,
  ...alertReviewHandlers,
  ...legalDisclaimerHandlers,
  ...cookieConsentHandlers,
  ...onboardingSampleProjectHandlers,
  ...s312A11yResponsiveHandlers,
];
