/**
 * Public API of the dare-widget package.
 *
 * tsup bundles everything reachable from this file into dist/. Anything not
 * re-exported here is package-internal. The main entry is `DareWidget`; the rest
 * is for advanced consumers (rendering AttributionView directly, tuning the
 * calibration, or typing a response).
 */

// The drop-in component (the normal entry point).
export { DareWidget } from "./DareWidget";
export type { DareWidgetProps } from "./DareWidget";

// The pure view + its calibration knobs, for consumers who already have a
// RecordSummary (e.g. from their own backend proxy) and want to render it.
export { AttributionView, DEFAULT_CALIBRATION } from "./AttributionView";
export type { AttributionViewProps, Calibration } from "./AttributionView";

// The network client + its typed error, for custom flows.
export { attribute, DareApiError } from "./api";
export type { AttributeOptions } from "./api";

// Data-contract types (mirror the DARE backend).
export type { DareChunk, AttributeRequest, RecordSummary } from "./types";
