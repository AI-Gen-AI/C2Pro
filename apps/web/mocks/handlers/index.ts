import { healthHandler } from "./custom/health";
import { demoDataHandlers } from "./custom/demo-data";
import { processingStreamHandler } from "./custom/processing-stream";
import { uploadHandlers } from "./custom/uploads";
import { alertReviewHandlers } from "./custom/alert-review";

export const handlers = [
  healthHandler,
  processingStreamHandler,
  ...demoDataHandlers,
  ...uploadHandlers,
  ...alertReviewHandlers,
];
