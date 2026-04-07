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
export function startPolling({ loadPrinterStatus, loadCFS }) {
  setInterval(loadPrinterStatus, 10_000);
  setInterval(loadCFS, 30_000);

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      loadPrinterStatus();
      loadCFS();
    }
  });
}
