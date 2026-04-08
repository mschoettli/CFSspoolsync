/** Polling utilities for periodic refreshes. */

/**
 * Start periodic refresh loops and visibility-based refresh.
 *
 * Args:
 * -----
 *     handlers (object):
 *         Callback collection for polling.
 *
 * Returns:
 * --------
 *     void:
 *         Registers interval handlers.
 */
export function startPolling({ loadPrinterStatus, loadCFS, loadSpools }) {
  setInterval(loadPrinterStatus, 5_000);
  setInterval(loadCFS, 5_000);
  if (typeof loadSpools === "function") {
    setInterval(loadSpools, 5_000);
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      loadPrinterStatus();
      loadCFS();
      if (typeof loadSpools === "function") {
        loadSpools();
      }
    }
  });
}
