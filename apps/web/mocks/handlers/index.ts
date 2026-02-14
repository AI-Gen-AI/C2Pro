import { healthHandler } from "./custom/health";
import { demoDataHandlers } from "./custom/demo-data";
import { processingStreamHandler } from "./custom/processing-stream";

export const handlers = [
  healthHandler,
  processingStreamHandler,
  ...demoDataHandlers,
];
