/** API helper functions for backend calls. */

const API_BASE = "";

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

  const response = await fetch("/api/scan-label", { method: "POST", body: fd });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "OCR request failed");
  }

  return response.json();
}
