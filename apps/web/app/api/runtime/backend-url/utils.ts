export function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

export function normalizeAbsoluteApiBaseUrl(rawValue: string | undefined): string | null {
  const value = rawValue?.trim();

  if (!value || value.startsWith("/")) {
    return null;
  }

  const normalized = trimTrailingSlash(value);

  if (normalized.endsWith("/api/v1")) {
    return normalized;
  }

  if (normalized.endsWith("/api")) {
    return `${normalized}/v1`;
  }

  return `${normalized}/api/v1`;
}
