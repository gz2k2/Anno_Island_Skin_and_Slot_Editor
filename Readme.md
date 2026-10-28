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

## Detailed workflow

The recommended workflow is **source → working copy → edit → validate/pack → export**. Keep source libraries, working maps, and release/export maps separate.

### 1. Configure Settings > Map Folders
Configure the paths you need before creating a working island. **Original Maps** and **Custom Map Folder** are sources, **Temporary Map Folder** is the working-copy destination, and **Map Export Folder** is the final filtered output root.

### 2. Create a working island
In **Start > Create Custom Island**, choose either **Create from Original Maps** or **Create from CustomFolder**. Original Maps uses the indexed original-map library; CustomFolder lets you choose an `.a7m` from your configured custom source library.

Enter **New folder / Map Name**. The default is `<selected a7m stem>_skinned`. The application copies the selected map variant into `<Temporary Map Folder>/<New Map Name>`, renames map-owned files and matching map-name directory components, preserves shared containers such as `_gamedata`, and selects the newly created `.a7m` as the active working island.

If you already have a working copy, you can select its `.a7m` directly instead of creating another copy.

### 3. Check Files and Folders
Verify that the selected `.a7m` and its companion files belong to the intended working map. Keep the complete directory structure together because later workflows use related map files and subfolders.

### 4. Configure regional conversion and textures
Use **Regional Settings** for target-region/material settings. If required, use **Texture Settings / Tintmaps** to convert supported DDS tintmaps and optionally apply Normal, Brighter, or Darker brightness handling. The native `bc7enc-py` path accelerates DXT1/BC1 encoding when available.

### 5. Edit objects
Use **Object Configuration** for filtering, replacement, density changes and custom-object workflows. Use **Object Map** for spatial selection, adding/removing/moving objects and area-based editing. Supported preview workflows keep edits in RAM until **Save** is used.

### 6. Edit slots
Use **Slot Configuration / Slot Map** for river, mine and supported resource/deposit slots. MapName and Gamedata changes are handled together where required. Review validation information and use **Save** to commit the working state.

### 7. Validate and pack
Review XML, ObjectId, GUID, MapName/Gamedata and slot warnings before finalization. If your edits need to be represented in packed island data, run **Pack Island Data** before exporting. **Export Map copies the existing packed map files and does not replace the packing step.**

### 8. Finalize > Export Map
1. Click **Export Map**.
2. Confirm/edit **New Folder / Map Name**. The current `.a7m` stem is pre-filled.
3. The output becomes `<Map Export Folder>/<Map Name>`.
4. Map-owned root files and matching map-name folders are renamed consistently to the export name.
5. Editing artifacts such as XML working files, `.data`, original/backup artifacts and `_tintmap_variants` are filtered out. `.xml.lnk` files are kept.
6. The export is staged before an existing confirmed destination is replaced.
7. After success, **Open folder?** can open the finished folder in Windows Explorer.

### 9. Export custom content when required
**Export custom content files** is separate from Export Map. Use it when the island needs a custom material set or custom `.prp` objects. It exports the selected/used content rather than blindly copying the complete custom-object library.

## Application areas

### Start / Files and Folders

These workflows select the island data used by the editor and provide the paths required by later operations.

The application supports folder-based map workflows and can work with original map sources as well as custom map directories. Keep the full source directory structure intact because multiple workflows rely on related files rather than a single isolated XML file.

### Settings > Map Folders

The four Map Folders have **different roles**. They should be understood as a pipeline, not as interchangeable paths.

```text
SOURCE LIBRARIES                 WORKING COPY                 FINAL OUTPUT
Original Maps ---------\
                         >---- Temporary Map Folder -----> Map Export Folder
Custom Map Folder -----/          edit here                 clean export
```

A practical layout is:

```text
D:/AnnoModding/
├── OriginalMaps/       <- Original Maps
├── CustomSources/      <- Custom Map Folder
├── WorkingMaps/        <- Temporary Map Folder
└── ExportedMaps/       <- Map Export Folder
```

#### Original Maps
**Purpose:** source library for extracted original Anno islands.

**Used by:** **Start > Create Custom Island > Create from Original Maps**.

The application recursively scans this root for `.a7m` files and available `mapimage.png` previews. The scan data is written to `original_maps_index.csv` beside the application and is used by the original-map selection popup. If a source contains several variants, you select the variant that should become the basis of your working island.

Treat this folder as a **master source library**. The workflow copies the selected island out of this library. You normally should not use Original Maps as your active editing folder or as the export destination.

Example:

```text
D:/AnnoModding/OriginalMaps/
└── ... extracted map tree ...
    ├── moderate_l_01.a7m
    └── mapimage.png
```

#### Custom Map Folder
**Purpose:** source library for your own prepared/extracted maps.

**Used by:** **Start > Create Custom Island > Create from CustomFolder**.

Use this when the source is not supposed to come from the indexed Original Maps tree. Typical examples are manually extracted islands, reusable base maps, maps from another modding workspace, or prepared source templates.

The chosen `.a7m` is **not edited in place by the Create Custom Island workflow**. It is used as the source for a new copy under Temporary Map Folder.

Do not confuse this with **Settings > Custom > Custom Objects Folder**. Custom Map Folder contains complete map sources; Custom Objects Folder contains custom `.prp` assets.

#### Temporary Map Folder
**Purpose:** destination for the editable working copies created by **Create Custom Island**.

Despite the word “Temporary”, this is effectively the application's **Working Maps** root. A created project can remain here while you edit it.

If you select `moderate_l_01.a7m` and enter `MyIsland` as **New folder / Map Name**, the workflow creates a structure such as:

```text
<Temporary Map Folder>/
└── MyIsland/
    ├── MyIsland.a7m
    ├── MyIsland/
    │   └── ... map-specific data ...
    ├── _gamedata/
    │   └── ... shared data ...
    └── ...
```

The creation routine does more than rename the outer folder. Map-owned root files and directory components belonging to the selected variant are changed from the old map name to the new map name. Shared structural folders such as `_gamedata` keep their shared names. The newly created `.a7m` becomes the active file in Start/Files and Folders.

This separation is intentional: **Original Maps / Custom Map Folder remain sources; Temporary Map Folder contains the copy you actually modify.**

#### Map Export Folder
**Purpose:** root directory for the cleaned output from **Finalize > Export Map**.

This setting should point to a parent directory, not to a single map project. Export Map asks for the map name and creates:

```text
<Map Export Folder>/<Map Name>/
```

Example:

```text
Map Export Folder = D:/AnnoModding/ExportedMaps
Map Name          = MyIsland_Final

Result:
D:/AnnoModding/ExportedMaps/MyIsland_Final/
```

The export name is also applied to matching map-owned root files and map-name directory components. Therefore an edited working map can be exported under a different final name while keeping its map-specific names consistent.

Export Map is a **filtered release/output copy**, not another working-copy command. It excludes the configured development artifacts, stages the complete export first, and only then replaces an existing destination after confirmation. After success, **Open folder?** opens the specific exported map folder.

Do not place Map Export Folder inside the map currently being edited. The exporter rejects source/destination paths that overlap or contain one another.

#### Quick decision guide

- Original extracted game map? → put/browse it under **Original Maps**.
- Own reusable or prepared source map? → use **Custom Map Folder**.
- Map you are actively changing? → create/use it under **Temporary Map Folder**.
- Finished filtered map for your output/mod workflow? → create it under **Map Export Folder**.

Example end-to-end path:

```text
Original Maps/.../moderate_l_01.a7m
        |
        | Create Custom Island, name: MyIsland
        v
Temporary Map Folder/MyIsland/MyIsland.a7m
        |
        | edit -> Save -> validate -> Pack Island Data
        v
Finalize > Export Map, name: MyIsland_Final
        |
        v
Map Export Folder/MyIsland_Final/MyIsland_Final.a7m
```

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
