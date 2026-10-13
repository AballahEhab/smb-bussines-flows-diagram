# SMB business-flow diagrams

Open [index.html](index.html) in a browser. The viewer is self-contained and works
offline: no server, internet connection, JavaScript package installation, or app
build is required. Begin with **Flutter login**, then select a journey family or
use the sidebar to open a detailed diagram.

The Codex in-app browser accepts HTTP URLs rather than direct local-file URLs.
For that browser, run the artifact-only local preview below and open
`http://127.0.0.1:18769/`. It serves only the generated viewer, binds to loopback,
and does not expose a directory listing or arbitrary source files.

```sh
python3 docs/business-flow-diagrams/scripts/preview.py
```

Blue means **Flutter UI**, orange means **Android/iOS native UI**, yellow diamonds
are **conditions**, purple ellipses are **SDK/external services**, and gray marks
unresolved destinations or documentation links. Platform text and shapes remain
visible alongside the colors. Flutter-hosted webviews and PDF screens are blue.

## Explore

- Search business names or class names; select a result to open its journey and
  focus that screen. A shared screen retains one identity across journey views.
- Select a screen, condition, or arrow for implementation names, exact predicates,
  callers/destinations, and source paths with one-based line numbers.
- Drag the canvas or use its arrow keys to pan. Use `+`/`−` or Control/Command
  plus the mouse wheel to zoom. **Fit all** shows the entire diagram;
  **Readable view** restores a comfortable text size.
- **Export SVG** offers a download and the exact SVG source for the selected
  diagram. If an embedded browser does not handle downloads, select/copy the
  source into the named `.svg` file. The editable Graphviz `.dot` and generated
  `.svg` files are also available in `diagrams/`.
- **Coverage & unresolved** lists inventoried screens, UI candidates, route and
  channel surfaces, and their explicit classifications. “Unresolved” does not
  mean unused; it means a complete navigation chain has not been established
  here. Search and platform/classification filters also work in this view.
- **Source snapshot** shows checkout versions and limitations. Native login
  fallbacks remain in the reconciliation inventory as obsolete; they do not
  appear in active diagrams.

Overview arrows are documentation links, not app transitions. Detailed graphs
represent source-supported navigation. Conditions may depend on backend menus,
roles, migration status, selected accounts, configuration, or API results. Both
configured alternatives are shown; a “current flag default” marker is used only
when the checked-in code establishes it. A runtime-null fallback is not proof of
production configuration.

## Sources and boundaries

The map uses the current Flutter checkout and the populated native siblings
`smb_android-cherry-pick-compatibility-2026-09-24` and
`smb_ios-cherry-pick-compatibility-2026-09-24`. The nominal native directory names
containing `6.0.0` are empty. Exact revisions, branches and working-tree status are
recorded in `graph.json`; the existing audits are coverage leads, not authorities
for current navigation.

Android/iOS screens remain separate identities in combined business journeys.
Inbound method-channel registrations, source references, and screen declarations
alone do not establish a live user journey. Empty handlers and unresolved vendor
destinations are identified explicitly. Backend-only menus, remote portal pages,
and device-only execution require runtime evidence and are not presented as
verified screens. This package does not change application behavior.

## Edit and regenerate

Requirements for regeneration: Python 3.9+ and Graphviz `dot` on `PATH`. The
delivered viewer needs neither.

From the Flutter repository root:

```sh
# Validate and render edits made directly to graph.json.
python3 docs/business-flow-diagrams/scripts/validate.py
python3 docs/business-flow-diagrams/scripts/build.py

# Rebuild graph.json from the source-checked authoring modules in flows/.
# This replaces manual graph.json edits.
python3 docs/business-flow-diagrams/scripts/build.py --refresh-data

# Check the validator's rejection of corrupt graphs and stale evidence.
python3 docs/business-flow-diagrams/scripts/test_validation.py
python3 docs/business-flow-diagrams/scripts/scenario_checks.py
```

`graph.json` holds canonical nodes, edges, journey membership, source evidence,
configuration conditions, snapshots, and reconciliation classifications.
`flows/*.py` contains the reviewed authoring definitions; the builder checks
source declarations and quoted evidence during regeneration. Preserve source
locations when adding a transition and keep untraced destinations gray.

`qa/validation.json` records structural/source checks. `qa/source_before.json` and
`qa/source_after.json` compare revisions, tracked status, and tracked-diff hashes
across all three repositories, including preservation of pre-existing changes.
Browser checks are recorded separately in `qa/browser_checks.md`.

No application builds or device journey tests are required by these documentation
changes. They would be required to claim production execution rather than
source-supported routing.
