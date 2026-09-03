# Widgets

<!-- lead: Project-local web extensions loaded from research materials. -->

<div class="media-slot" data-media="widgets-hero" data-accept="png,jpg,webp,mp4,webm"><p>Media: widgets</p></div>

## How it works

A widget is a package under the research project:

```text
koi-structure/widgets/<id>/
├── widget.json
├── README.md
└── web/
    ├── index.js
    └── optional assets
```

The manifest declares identity, web entry point, surfaces, and default enablement. The loader imports the entry and calls its `mount` function with project context and API helpers.

## How people use the interface

1. Enabled packages appear automatically on the main workspace, often as floating elements over the map.
2. Enable or inspect them through the CLI or API:

```bash
python -m widgets.base.cli list
python -m widgets.base.cli enable <widget-id>
```

3. To add one, place a valid package in `koi-structure/widgets/`, commit it to the research branch, and reload.
4. Hub is intended to publish reusable packages; active development remains local to a project.

## Agent workflows

Widgets do not require an Inbox workflow. An IDE agent edits `widgets/<id>/` according to its README and manifest contract. Hub catalog browsing and downloads are planned; current use is project-local.

## Technical details

| Location | Responsibility |
|---|---|
| `ReseachOS/widgets/base/` | manifest, registry, CLI, and `floating.js` |
| `tree/…/koi-structure/widgets/` | researcher packages |
| `web/widgets-loader.js` | loading and mounting |
| `#koi-widgets-root` | page container |
| `api/routers/widgets.py`, `api/web_proxy.py` | catalog, data, and static files |

```js
export function mount(root, context) {
  // render into root; return optional cleanup function
}
```

A package without a valid manifest and `entry.web` is not exposed. Enablement is local in `.run/widgets.json`, so colleagues enable a widget separately unless `default_enabled` changes. Desktop surfaces are reserved; the current loader targets web.

Related: [PaperDraft](paper.html) · [Run monitor](monitor.html) · [Architecture](index.html)
