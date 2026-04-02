/**
 * Test Suite ID: TASK-1446
 * Purpose: Vitest-compatible MSW shim for local mock handlers.
 */

export type PathParams = Record<string, string>;

export type ResponseResolver = (args: {
  params: PathParams;
  request: Request;
}) => Response | Promise<Response>;

export interface MockHandler {
  info: {
    method: string;
    path: string;
  };
  match(request: Request): PathParams | null;
  resolver: ResponseResolver;
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function compilePath(pathname: string): {
  regex: RegExp;
  paramNames: string[];
} {
  const normalized = pathname.startsWith("*")
    ? pathname.slice(1)
    : pathname;
  const paramNames: string[] = [];
  const pattern = normalized
    .split("/")
    .map((segment) => {
      if (!segment) {
        return "";
      }
      if (segment.startsWith(":")) {
        paramNames.push(segment.slice(1));
        return "([^/]+)";
      }
      return escapeRegex(segment);
    })
    .join("/");

  return {
    regex: new RegExp(`^${pattern}$`),
    paramNames,
  };
}

function createHandler(method: string) {
  return (path: string, resolver: ResponseResolver): MockHandler => {
    const { regex, paramNames } = compilePath(path);

    return {
      info: {
        method,
        path,
      },
      match(request: Request): PathParams | null {
        if (request.method.toUpperCase() !== method) {
          return null;
        }

        const url = new URL(request.url);
        const match = regex.exec(url.pathname);
        if (!match) {
          return null;
        }

        return Object.fromEntries(
          paramNames.map((name, index) => [name, decodeURIComponent(match[index + 1] ?? "")]),
        );
      },
      resolver,
    };
  };
}

export class HttpResponse extends Response {
  static json(data: unknown, init?: ResponseInit): HttpResponse {
    return new HttpResponse(JSON.stringify(data), {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  }
}

export const http = {
  get: createHandler("GET"),
  post: createHandler("POST"),
  patch: createHandler("PATCH"),
  delete: createHandler("DELETE"),
};

export function setupWorker() {
  return {
    start: async () => undefined,
    stop: async () => undefined,
    resetHandlers: () => undefined,
    use: () => undefined,
  };
}
