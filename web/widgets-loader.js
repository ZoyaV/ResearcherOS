/**
 * Load enabled widgets from /api/widgets into #koi-widgets-root.
 * Packages live in koi-structure/widgets/; ResearchOS only hosts base + API.
 */

export async function initWidgets({ api, skip = false } = {}) {
  if (skip) return;
  const root = document.getElementById("koi-widgets-root");
  if (!root) return;

  let catalog;
  try {
    catalog = await api.listWidgets();
  } catch (err) {
    console.warn("[widgets] catalog unavailable", err);
    return;
  }

  const items = Array.isArray(catalog?.widgets) ? catalog.widgets : [];
  const enabled = items.filter((w) => w.enabled && w.web_url);

  for (const item of enabled) {
    const host = document.createElement("div");
    host.className = "koi-widget-host";
    host.dataset.widgetKey = item.key;
    host.dataset.widgetId = item.id;
    root.appendChild(host);
    const assetBase = item.web_url.replace(/\/[^/]+$/, "");
    try {
      const mod = await import(/* webpackIgnore: true */ item.web_url);
      if (typeof mod.mount !== "function") {
        console.warn(`[widgets] ${item.key}: no mount() export`);
        continue;
      }
      await mod.mount(host, {
        api,
        widgetId: item.id,
        widgetKey: item.key,
        assetBase,
        manifest: item,
      });
    } catch (err) {
      console.warn(`[widgets] failed to mount ${item.key}`, err);
    }
  }
}
