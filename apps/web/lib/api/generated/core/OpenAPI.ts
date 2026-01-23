export type OpenAPIConfig = {
  BASE: string;
  VERSION: string;
  WITH_CREDENTIALS: boolean;
  CREDENTIALS: "include" | "omit" | "same-origin";
  TOKEN?: string | (() => Promise<string>);
};

export const OpenAPI: OpenAPIConfig = {
  BASE: "",
  VERSION: "0.0.0",
  WITH_CREDENTIALS: false,
  CREDENTIALS: "include",
};
