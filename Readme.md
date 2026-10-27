# Anno Island Reskinner

> **AI-generated documentation:** This README was created with AI assistance and should be reviewed and improved where necessary. Contributions and corrections are welcome.

[☕ Support development on Ko-fi](http://www.ko-fi.com/gz2k2)

**Anno Island Reskinner** is a desktop tool for editing, reskinning, adapting, validating, and exporting Anno 1800 island/map data. It combines regional conversion, material-set handling, tintmap patching, custom content, object editing, slot editing, XML validation/repair, and map export in one application.

> **Important:** Always work on copies of your island and modding data. Some workflows intentionally write patched files or export generated data.

## Features

- Select and manage island/map files from `.a7m` projects
- Create working maps from original map data or custom map folders
- Convert regional settings between **Old World**, **New World**, **Enbesa**, and **Arctic**
- Select, manage, and export material sets
- Patch DDS tintmaps for regional conversions and brightness variants
- Inspect, filter, replace, and edit RD3D objects
- Add and manage custom objects, categories, and regions
- Edit object placement visually in **Object Map**
- Edit river, mine, deposit, and other supported slots in **Slot Map**
- Keep supported map edits in RAM until **Save** is explicitly used
- Validate and repair supported XML/slot structures
- Export cleaned map data for use in a mod project
- Export only the custom content actually used by the current island

## Typical workflow

1. Select or create the island/map project in **Start** / **Files and Folders**.
2. Configure paths and application settings if required.
3. Select the target region and material set.
4. Patch tintmaps if the island is being visually converted to another region.
5. Adjust objects in **Object Configuration** and **Object Map**.
6. Adjust island slots in **Slot Configuration** and **Slot Map**.
7. Review validation results and warnings.
8. Save the desired map/object/slot changes.
9. Use **Finalize** to export the map and any required custom content.

## Application areas

### Start / Files and Folders

These workflows select the island data used by the editor and provide the paths required by later operations.

The application supports folder-based map workflows and can work with original map sources as well as custom map directories. Keep the full source directory structure intact because multiple workflows rely on related files rather than a single isolated XML file.

### Regional Settings

Regional conversion settings allow the island to be adapted between:

- Old World
- New World
- Enbesa
- Arctic

Regional conversion can affect multiple independent parts of an island, including material sets, object data, slots, and tintmaps.

### Texture Settings / Tintmaps

The tintmap workflow patches supported DDS tintmaps for a selected source and target region.

Brightness modes include:

- **Normal**: regional conversion without an extra brightness offset
- **Brighter**: adds the configured positive RGB offset
- **Darker**: adds the configured negative RGB offset

The patcher uses backups and patch-state information to avoid unintentionally applying the same conversion repeatedly. If a tracked DDS file was changed externally, the application can report a conflict instead of silently overwriting it.

Tintmap processing may create an internal helper/cache directory named:

```text
_tintmap_variants/
```

This directory is used by the editing workflow and is **not included by Export Map**.

### Material Sets

Material sets can be selected and handled as part of the regional/finalization workflow.

When **Export custom content files** exports the active material set, the resulting structure is:

```text
<export folder>/
└── data/
    └── config/
        └── engine/
            └── material_sets/
                ├── <name>.materialset
                └── <name>.xml.lnk
```

The `.xml.lnk` points to:

```text
data/config/engine/material_sets/<name>.materialset
```

### Custom Content

The **Custom Content** workflow allows user-defined objects, categories, and regions to be integrated into the existing object-selection and editing workflows.

Custom definitions are stored separately from the built-in object database, so the base database does not need to be modified for every custom object.

The application can merge custom objects dynamically into object tables, category pickers, replace workflows, and place-object workflows.

#### Custom Objects Folder

The **Custom Objects Folder** contains the physical custom object files referenced by the custom object definitions.

When **Export custom content files** is used, the application does **not** blindly copy the entire Custom Objects Folder. It exports the custom objects that are registered and actually used by the current island.

For every used `.prp`, its directory structure relative to the configured Custom Objects Folder is preserved.

Example source:

```text
<Custom Objects Folder>/
└── data/
    └── graphics/
        └── props/
            └── custom/
                └── example.prp
```

Export result:

```text
<export folder>/
└── custom_objects/
    └── data/
        └── graphics/
            └── props/
                └── custom/
                    └── example.prp
```

This allows exported custom object files to retain the directory hierarchy in which they were found.

### Object Configuration

The **Object Configuration** tab contains table-based tools for inspecting and modifying object data used by the island.

Supported workflows include:

- filtering objects and categories
- mass replacement
- GUID/object replacement
- density changes
- custom object integration
- opening the visual Object Map

### Object Map

The **Object Map** provides a visual representation of object positions.

Depending on the current editing state it supports:

- category-aware object coloring
- filtering visible object categories
- rectangle selection
- Ctrl-based lasso selection
- adding objects
- removing objects
- changing object density inside a selected area
- moving supported dots
- moving selected objects together
- previewing edits before saving
- Save / Reload / Reset workflows

Map editing is designed around a RAM working state where supported changes remain unsaved until the corresponding **Save** action is used.

### Slot Configuration / Slot Map

Slot editing covers supported island slot data such as river, mine, and resource/deposit slots.

The visual **Slot Map** can provide operations for:

- selecting slots
- adding slots
- removing slots
- moving slots
- rotating supported slots
- changing GUIDs
- rectangle/lasso selection
- validating MapName/Gamedata relationships
- Save / Reload / Reset workflows

Slot Map changes are kept in a working state and are written by the explicit Save workflow. Validation is performed before synchronized XML changes are installed.

### Validation and XML repair

The project contains dedicated validation and repair functionality for supported XML structures.

Validation is especially important when MapName and Gamedata references are changed. Do not ignore reported mismatches blindly. Review GUID, ObjectId, position, and slot-integration warnings before distributing an exported island.

## Finalize and Export

### Export Map

**Export Map** creates a filtered copy of the selected map directory.

The export intentionally excludes development/editing artifacts such as supported backup/original data and XML working files according to the export filter.

In addition, the following tintmap helper directory is explicitly excluded wherever it occurs in the map tree:

```text
_tintmap_variants/
```

The export is staged before replacing an existing confirmed destination. This reduces the chance that a cancelled or failed export destroys the previous exported map.

### Export custom content files

This export is separate from **Export Map** and collects the additional content required by the current island.

It can export:

- the selected material set
- the corresponding `.xml.lnk`
- used custom `.prp` objects

Material sets are exported under:

```text
data/config/engine/material_sets/
```

Custom objects are exported under:

```text
custom_objects/
```

with their directory hierarchy relative to **Custom Objects Folder** preserved.

Only custom object files actually used by the current island are included.

## Project structure

The application source is organized as a Python package:

```text
Anno Island Reskinner.py
00_build_onefile.py
version.txt

app/
├── main.py
├── backend/
│   └── xml_backend.py
├── config/
│   ├── config_colors.py
│   ├── config_gamedata.py
│   ├── config_rd3d.py
│   └── config_slot.py
├── database/
│   └── database_props.py
├── functions/
│   ├── function_custom_content.py
│   ├── function_density.py
│   ├── function_island_slots.py
│   ├── function_map_export.py
│   ├── function_map_selection.py
│   ├── function_place_object.py
│   ├── function_region.py
│   ├── function_slot_validation.py
│   ├── function_xml_repair.py
│   └── functions_tintmaps.py
├── templates/
│   ├── template_category_picker.py
│   ├── template_map_view.py
│   ├── template_popup.py
│   ├── template_profiles.py
│   ├── template_statuswindow.py
│   ├── template_table.py
│   └── template_treeview.py
└── ui/
    ├── ui.py
    └── tabs/
        ├── ui_tab_custom_content.py
        ├── ui_tab_files_and_folders.py
        ├── ui_tab_finalize.py
        ├── ui_tab_helpers.py
        ├── ui_tab_material_sets.py
        ├── ui_tab_object_configuration.py
        ├── ui_tab_regional_settings.py
        ├── ui_tab_settings.py
        ├── ui_tab_slot_configuration.py
        ├── ui_tab_start.py
        └── ui_tab_texture_settings.py

tests/
├── test_native_deposit_integration.py
├── test_original_deposit_variants.py
├── test_slot_validation.py
└── test_xml_repair.py
```

Each Python package directory contains its own `__init__.py`.

The `tests/` package is for development/testing and is not required by the application at runtime.

## Running from source

A Python environment with the application's dependencies is required. The GUI uses CustomTkinter/Pillow and the current XML backend uses lxml.

Start the application from the project root with:

```bash
python "Anno Island Reskinner.py"
```

For development, run tests from the project root with:

```bash
python -m pytest
```

## Building the Windows executable

The repository contains:

```text
00_build_onefile.py
```

It validates the expected project/package structure and builds the Windows application with PyInstaller.

Run:

```bash
python 00_build_onefile.py
```

The application version is read from:

```text
version.txt
```

If `version.txt` contains:

```text
0.107.24
```

the generated executable is named:

```text
Anno_Island_Reskinner_0.107.24.exe
```

The build is written to the `dist/` directory.

The `tests/` package is intentionally excluded from the application executable.

## GitHub releases

The GitHub Actions release workflow uses `version.txt` as the release version and calls the same `00_build_onefile.py` builder used for local builds.

For a tagged release, the Git tag should match the version in `version.txt`:

```text
version.txt: 0.107.24
Git tag:     v0.107.24
```

A mismatch is intended to stop the release workflow rather than publishing an incorrectly versioned executable.

## Safety and project notes

- Keep backups of original islands and mod data.
- Prefer working on copies rather than irreplaceable game/modding files.
- Test exported islands in a development/test mod before distribution.
- Keep the complete source folder structure available while editing.
- Do not manually remove tintmap backup/state files unless you understand how this affects later patch operations.
- Remember that regional settings, material sets, tintmaps, RD3D objects, and slots are separate layers of the conversion workflow.
- Review validation warnings before final export.
- Use the status/progress windows for long operations instead of assuming the application has stalled.

## Contributing

Bug reports, corrections, documentation improvements, and code contributions are welcome.

Because this README was initially AI-generated, manual review and corrections are especially appreciated whenever application behavior changes.

## Support

If the tool is useful to you and you want to support continued development:

**Ko-fi:** [http://www.ko-fi.com/gz2k2](http://www.ko-fi.com/gz2k2)
