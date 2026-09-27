/**
 * FROZEN V1 well-viewer classification (pre construction dual-label).
 * Extracted from index.html 2026-07-21. Do not edit.
 * Revert: set window.DNR_CLASSIFY_VERSION = 'v1' before scripts run,
 * or load this file and call DnrClassifyV1.* instead of V3.
 */
(function (global) {
  'use strict';
  // NOTE: These are snapshots of the pure decision logic; they depend on
  // lithoDepthToRock, getWellDisplayDepthFt, etc. from index.html when used live.
  // Prefer re-enabling the inlined v1 branches via DNR_CLASSIFY_VERSION=v1.

  global.DnrClassifyV1 = {
    version: 'viewer-classify-v1-2026-07-21',
    notes: 'Frozen snapshot — short-circuits estimated; aquifer-text uncon; residual rock'
  };
})(typeof window !== 'undefined' ? window : globalThis);
