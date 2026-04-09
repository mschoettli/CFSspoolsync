/** API helper functions for backend calls. */

const API_BASE = "";
const OCR_TIMEOUT_MS = 120_000;

/**
 * Execute a JSON API call and raise on non-2xx responses.
 *
 * Args:
 * -----
 *     path (string):
 *         Relative API path.
 *     opts (RequestInit):
 *         Fetch options.
 *
 * Returns:
 * --------
 *     Promise<any>:
 *         Parsed JSON response.
 *
 * Raises:
 * -------
 *     Error:
 *         Raised when the request fails.
 */
export async function apiFetch(path, opts = {}) {
  const response = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || response.statusText);
  }

  return response.json();
}

/**
 * Upload a label image to the OCR endpoint.
 *
 * Args:
 * -----
 *     file (Blob | File):
 *         Image to scan.
 *
 * Returns:
 * --------
 *     Promise<any>:
 *         Parsed OCR data.
 *
 * Raises:
 * -------
 *     Error:
 *         Raised when OCR endpoint call fails.
 */
export async function uploadLabelImage(file) {
  const fd = new FormData();
  fd.append("file", file, "label.jpg");

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), OCR_TIMEOUT_MS);
  let response;
  try {
    response = await fetch("/api/scan-label", {
      method: "POST",
      body: fd,
      signal: controller.signal,
    });
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error(`OCR-Analyse Timeout (${Math.round(OCR_TIMEOUT_MS / 1000)}s). Bitte erneut versuchen.`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
  if (!response.ok) {
    const text = await response.text();
    let detail = "OCR request failed";
    if (text) {
      try {
        const payload = JSON.parse(text);
        detail = payload.detail || payload.message || detail;
      } catch {
        detail = text;
      }
    }
    throw new Error(detail);
  }

  return response.json();
}
