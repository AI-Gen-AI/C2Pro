import { setupServer } from "msw/node";
import { handlers } from "./handlers";
import { seedDemoData } from "./data";

seedDemoData();

export const server = setupServer(...handlers);
