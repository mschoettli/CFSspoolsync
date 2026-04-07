/** Global frontend state. */

export const state = {
  view: "cfs",
  cfs: [],
  spools: [],
  jobs: [],
  printer: {},
  filterStatus: "",
  jobsStatusFilter: "",
  jobsSortBy: "recent",
  lastSyncAt: null,
  lastSyncStatus: "idle",
};
