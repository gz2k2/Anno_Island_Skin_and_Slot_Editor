# Anno Island Reskinner

> **Note:** This README was generated with AI. I would really appreciate it if someone took the time to review it and improve it in a meaningful way. Contributions and corrections are very welcome.

[☕ Support development on Ko-fi](http://www.ko-fi.com/gz2k2)

**Anno Island Reskinner** is a desktop tool for editing, reskinning, adapting, and exporting Anno island/map data. It combines regional conversion settings, material-set handling, object editing, slot editing, tintmap patching, validation, repair helpers, and map export in one interface.

> **Important:** Always work on a copy of your island/map data. The application edits game/modding assets and some operations write changes back to the selected files.

## Features at a glance

- Select and manage the island/map files used by the editor
- Change regional settings between **Old World**, **New World**, **Enbesa**, and **Arctic**
- Work with material sets
- Patch DDS tintmaps when converting an island to another region
- Configure map objects and replace object categories/GUIDs
- Use a visual **Object Map** to inspect and edit object placement
- Add, move, rotate, and remove supported objects from the map workflow
- Work with island slots through the **Slot Configuration** and visual **Slot Map** tools
- Validate and repair supported XML/slot structures
- Preview changes in RAM before saving in map-based workflows
- Export the processed map and related material-set data

---

## Application workflow

A typical workflow is:

1. Select the required island/map files in **Files and Folders**.
2. Configure the target region and material settings in **Regional Settings**.
3. Patch tintmaps when the island is being visually converted to another region.
4. Adjust objects in **Object Configuration** and **Object Map**.
5. Adjust coast, river, mine, and other supported slots in **Slot Configuration / Slot Map**.
6. Review warnings or validation results.
7. Save the modified data.
8. Use **Finalize** to export the resulting map/material data.

---

## Files and Folders

The **Files and Folders** tab is the starting point for selecting the island/map data the application operates on.

The selected A7M/map location is reused by later workflows such as Regional Settings, Object Configuration, Slot Configuration, tintmap patching, and map export.

For best results, keep the complete island directory structure intact rather than copying individual files out of their original folder hierarchy.

---

## Regional Settings

The **Regional Settings** tab controls the regional conversion of the selected island.

Supported regions include:

- Old World
- New World
- Enbesa
- Arctic

Regional settings are used when adapting an island created for one region so that it can be used with assets/settings from another region.

### Material Set

Regional Settings includes selection of the material-set configuration used for the island. Material-set data can also be handled through the dedicated **Material Sets** workflow.

### Patch Tintmaps

The **Patch Tintmaps** function modifies supported DDS tintmaps below the island's tintmap directory.

Select:

- **From:** source region
- **To:** target region
- **Brightness:** additional brightness treatment

Brightness options:

| Setting | Effect |
|---|---|
| `Normal` | Uses the normal regional conversion without an additional brightness offset |
| `Brighter` | Applies the configured positive RGB brightness offset |
| `Darker` | Applies the configured negative RGB brightness offset |

The brightness offsets are defined centrally in `functions_tintmaps.py`:

```python
BRIGHTER_RGB_OFFSET = (12, 12, 12)
DARKER_RGB_OFFSET = (-12, -12, -12)
```

The tintmap patcher maintains original backups and persistent patch state. Source region, target region, brightness mode, patch routine version, and file state are used to detect an already processed configuration. Repeating the same successful configuration therefore does not intentionally apply the same conversion cumulatively again.

If source and target region are identical and brightness is `Normal`, the patcher restores the original tintmap where an original backup is available.

---

## Material Sets

The **Material Sets** section is used to work with the material-set configuration associated with the island.

The application can prepare/export material-set data as part of the final modding workflow. Regional Settings and Material Sets are linked through the selected `MaterialSetFileName`.

---

## Object Configuration

The **Object Configuration** tab provides table-based tools for inspecting and modifying object data used by the island.

Available workflows include object/category filtering and replacement operations, including mass replacement of supported GUID/object references.

### Object Map

The **Object Map** provides a visual map representation of object positions.

It supports workflows such as:

- viewing object positions as colored dots
- category-aware coloring
- filtering the displayed objects
- selecting an area of objects
- adding objects
- moving supported dots when **Allow Dot Movement** is enabled
- moving all selected objects together when a selection area is active
- previewing edits before Save
- Reload / Reset / Save workflows

The normal selection rectangle is blue. When dot movement mode is active, the selection rectangle is displayed in red.

Clicking outside an existing selection area clears that selection. `Esc` can also clear the selection.

### Add / Place Object

Objects can be placed from the Object Map through the Add/Place Object popup.

The popup provides two selection modes:

- **Category**
- **Object**

The lists can be filtered by text and region. The Treeview columns can be sorted by clicking their headings. Entries use the same category coloring concept as the Object Map.

Select a row and use **Select** to accept the chosen category/object. For a category selection, the application uses the objects associated with that category for placement.

---

## Slot Configuration

The **Slot Configuration** tools are intended for editing island slot data and supported slot/object assignments.

The editor contains dedicated handling for slot types used by the island data, including river and mine related workflows and GUID replacement operations.

### Slot Map

The visual **Slot Map** allows supported slots to be inspected and edited directly on a map representation.

Depending on the selected slot type and available data, the map workflow contains operations for changing slot-related object data, rotation/orientation, selection, saving, reloading, and resetting edits.

Selection areas can be cleared with `Esc` or by left-clicking outside the existing selection rectangle.

---

## Validation and XML repair

The project contains dedicated validation and XML-repair functionality used by the editing workflows.

These checks are particularly important when slot/object changes would otherwise leave incompatible or incomplete XML structures. Validation warnings should be reviewed before final export instead of being ignored blindly.

---

## RAM-based editing and Save / Reload / Reset

Several map-editing workflows keep changes in an in-memory editing state before writing the changes to the island data.

This allows the map view to preview changes before **Save**.

Typical controls include:

- **Save**: write the current edits
- **Reload**: reload the relevant data
- **Reset**: discard/reset the current editing state for that workflow

Pay attention to status popups/messages while longer XML, RD3D, cache, tintmap, or export operations are running.

---

## Finalize and Export

The **Finalize** workflow prepares output from the edited island.

The project includes dedicated export handling for:

- map export
- material-set export

Map export writes the selected island/map data to the configured export destination. If the destination map folder already exists, the application can explicitly request replacement of that exported map folder.

Review any reported warnings before using the exported files in a mod project.

---

## Tintmap safety and repeat processing

Tintmap patching has additional safeguards because repeated color conversion would otherwise progressively alter the textures.

The patcher therefore uses:

- `.tintmap_original` backup files
- `tintmap_patch_state.json`
- SHA-256 checks
- source region
- target region
- brightness mode
- patch routine version

If a DDS covered by the stored patch state was modified externally, the patcher reports a conflict rather than silently overwriting the changed file.

---

## Notes for modding projects

- Keep backups of original islands and exported mod data.
- Test exported islands in a development/test mod before distributing them.
- Do not manually delete tintmap backup/state files unless you understand the effect on subsequent tintmap conversion.
- When moving an island between regions, remember that the workflow may involve several independent layers: regional settings, material sets, RD3D/object data, slots, and tintmaps.
- Use the visual map editors for spatial changes, but review the corresponding configuration/validation output before final export.

---

## Support

If the tool is useful to you and you want to support continued development:

**Ko-fi:** http://www.ko-fi.com/gz2k2

