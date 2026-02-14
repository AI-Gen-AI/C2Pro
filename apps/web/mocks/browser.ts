import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";
import { seedDemoData } from "./data";

seedDemoData();

export const worker = setupWorker(...handlers);
