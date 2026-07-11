import { MutationCache, QueryClient } from "@tanstack/react-query";
import { showToast } from "@/lib/ui/toast";

function detailToMessage(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim().length > 0) {
    return detail.trim();
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (
          typeof item === "object" &&
          item !== null &&
          "msg" in item &&
          typeof item.msg === "string"
        ) {
          return item.msg;
        }
        return null;
      })
      .filter((message): message is string => Boolean(message));

    return messages.length > 0 ? messages.join(", ") : null;
  }

  return null;
}

export function mutationErrorMessage(error: unknown): string {
  const maybeResponse = error as {
    response?: { data?: { detail?: unknown; message?: unknown } };
    data?: { detail?: unknown; message?: unknown };
    message?: unknown;
  };

  const detailMessage =
    detailToMessage(maybeResponse.response?.data?.detail) ??
    detailToMessage(maybeResponse.data?.detail);

  if (detailMessage) {
    return detailMessage;
  }

  const responseMessage = maybeResponse.response?.data?.message;
  if (typeof responseMessage === "string" && responseMessage.trim().length > 0) {
    return responseMessage.trim();
  }

  const dataMessage = maybeResponse.data?.message;
  if (typeof dataMessage === "string" && dataMessage.trim().length > 0) {
    return dataMessage.trim();
  }

  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }

  if (typeof maybeResponse.message === "string" && maybeResponse.message.trim().length > 0) {
    return maybeResponse.message.trim();
  }

  return "Action failed. Please try again.";
}

export const queryClientConfig = {
  mutationCache: new MutationCache({
    onError: (error, _variables, _context, mutation) => {
      if (
        typeof mutation.options.onError === "function" ||
        mutation.options.meta?.suppressGlobalErrorToast === true
      ) {
        return;
      }

      showToast(mutationErrorMessage(error));
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
    },
  },
};

export const createQueryClient = () => new QueryClient(queryClientConfig);
