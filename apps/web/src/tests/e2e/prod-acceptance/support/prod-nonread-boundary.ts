/** PQ-HITL-03: strict, non-secret production non-read classification.
 *
 * An opaque Next-Action ID, route, browser phase or 2xx/3xx HTTP response
 * cannot establish that a POST is a Clerk session operation. There are NO
 * exemptions without independently verified action provenance.
 */
const APP_HOSTS = new Set([
  "c2pro.io",
  "www.c2pro.io",
  "c2pro-production.up.railway.app",
]);

export type NonReadDisposition =
  | "read"
  | "unverified_external_nonread"
  | "unparseable_nonread"
  | "unverified_first_party_nonread";

export function classifyNonReadRequest(
  method: string,
  requestUrl: string,
): NonReadDisposition {
  if (["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase())) return "read";
  let url: URL;
  try {
    url = new URL(requestUrl);
  } catch {
    return "unparseable_nonread";
  }
  return APP_HOSTS.has(url.hostname)
    ? "unverified_first_party_nonread"
    : "unverified_external_nonread";
}
