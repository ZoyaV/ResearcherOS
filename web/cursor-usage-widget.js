/**
 * Legacy shim — widgets now load from koi-structure via widgets-loader.js.
 */

import { initWidgets } from "./widgets-loader.js";
import { KoiApi } from "./api.js";

/** @deprecated Prefer initWidgets from widgets-loader.js */
export async function initCursorUsageWidget() {
  await initWidgets({ api: KoiApi, skip: false });
}
