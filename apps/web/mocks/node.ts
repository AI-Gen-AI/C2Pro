import { setupServer } from "@/mocks/msw-node";
import { testHandlers } from "./handlers";
import { seedDemoData } from "./data";

seedDemoData();

export const server = setupServer(...testHandlers);
