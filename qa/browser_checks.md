# Viewer verification

Verified in the Codex in-app browser on 13 October 2026. Browser preview serves
only `index.html` at `http://127.0.0.1:18769/`; all diagrams and data are embedded.

| Check | Result |
| --- | --- |
| Overview starts at Flutter login | Passed; native login is absent from active diagrams. |
| Family links | Passed; selecting Shop lists its journeys and opens the device-purchase diagram. |
| Screen search | Passed; `AccountWithPartyIdScreen` finds the Flutter selector, opens its native-device journey, and focuses it. |
| Node details | Passed; class, platform, callers, destinations and current source location are displayed. |
| Conditional-arrow details | Passed; the device-selector branch displays the condition and both Android/Flutter call evidence. |
| Platform colors | Blue Flutter, orange Android/iOS native, yellow decisions and purple services verified in generated SVGs and viewer. |
| Native-to-Flutter return | Device account selection retains its native reservation continuation. |
| Zoom / keyboard pan | Zoom changed 100% → 125% → 100%; ArrowRight changed canvas translation. |
| Fit all | Entire largest notifications graph fits inside its canvas; readable view restores 100%. |
| SVG export | Export dialog contains a complete valid SVG, correct `.svg` filename, download link, and selectable source. All 16,893 characters of the device-diagram source were selected. |
| Inventory classification | Three obsolete native-login candidates shown; platform/classification/search filters and empty-result state verified. |
| Source snapshot | Displays Flutter/Android/iOS revisions, branches, source-location count and source-review limitations. |
| Desktop layout | Inspected at 1280 × 800; navigation, diagram, legend and details stay within their panels. |
| Narrow layout | Inspected at 390 × 844 and the app's normal narrow panel; no horizontal page overflow. Panels stack; inventory reasons remain visible. Diagram fit and readable zoom controls are available. |
| Offline dependencies | No external script, stylesheet, font, fetch, or XHR dependency in the generated viewer. |
| Console errors | None recorded during the checks. |

The in-app browser did not deliver a download event for the original automatic
Blob download. The shipped viewer therefore offers an explicit export dialog,
standard download link, and verified source-copy fallback. All SVGs are also
delivered under `diagrams/`; saving via an embedded browser's download manager is
not claimed verified.

`viewer-preview.png` records the final viewer in the app's normal narrow panel.
Temporary viewport overrides were reset, and the viewer tab was kept open as the
deliverable.

## Source and structural acceptance

- 72 diagrams: overview plus 71 detailed journeys; 665 canonical nodes, including
  535 screen identities, and 900 connections.
- 1,533 current source locations checked; no structural errors or directed-entry
  warnings. All 72 SVGs parse and contain their graph-data node/edge identities.
- All 17 scenario checks passed, including old/new Pay, guest flags, backend
  menus, role-based Manage, prepaid, BFM, and the device round trip.
- Seven validator tests passed: valid graphs, duplicate identities, dangling
  endpoints, stale evidence, empty decision branches, obsolete native login,
  and broken journey links.
- Source snapshots match across all three repositories: revisions, tracked
  status, and tracked-diff hashes are unchanged. Existing staged documents and
  the pre-existing planning package were preserved.

Inventory classification is reconciliation, not proof of runtime completeness:
795 reference candidates remain unresolved, 256 registry/channel surfaces have
no mapped producer chain, and 41 candidates are outside the older audited import
closure. These remain visible rather than being asserted active or dead. Eighteen
explicit unresolved destination nodes are included in the detailed diagrams.
Backend-only routes, remote portal content, and device execution remain outside
the verified source-navigation claims.
