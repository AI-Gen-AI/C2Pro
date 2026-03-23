import { setupWorker } from "msw/browser";
import { browserHandlers } from "./handlers";
import { seedDemoData } from "./data";

seedDemoData();

export const worker = setupWorker(...browserHandlers);
