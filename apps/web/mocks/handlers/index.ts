import { healthHandler } from "./custom/health";
import { processingStreamHandler } from "./custom/processing-stream";

export const handlers = [healthHandler, processingStreamHandler];
