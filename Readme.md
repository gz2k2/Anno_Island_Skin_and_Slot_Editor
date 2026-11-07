# Anno 1800 Island Skin and Slot Editor

[☕ Support development on Ko-fi](http://www.ko-fi.com/gz2k2)

The **Anno 1800 Island Skin and Slot Editor** is a desktop tool for preparing and editing island projects. It combines unpacking, regional settings, material sets, tint-map adjustment, object and slot editing, custom content, island packing, and filtered export.

> **Important:** Always work on copies of your island and modding data. Some workflows intentionally write patched files or export generated data.

## Contents

- [Detailed workflow](#detailed-workflow)
- [Settings](#settings)
- [Custom Content](#custom-content)
- [Helpers](#helpers)
- [Finalize and Export](#finalize-and-export)
- [Troubleshooting](#troubleshooting)
- [Running from source](#running-from-source)
- [Building the executable](#building-the-executable)

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
- Export used custom objects and configured custom material sets
- Copy the bundled Island Editor mod files into the Anno 1800 Mod folder
- Configure and use named custom single Slots and River Slots

## Linux

Release builds include a Linux archive (`*_linux_x86_64.tar.gz`) with the editor and self-contained `FileDBReader` / `RdaConsole` helper tools (no .NET install required).

```bash
tar -xzf Anno_Island_Skin_and_Slot_Editor_v<version>_linux_x86_64.tar.gz
./Anno_Island_Skin_and_Slot_Editor_v<version>
```

The tools in `./tools/` are detected automatically; otherwise set them under **Settings > General**. Set **Folder 'maindata'** to the game's `maindata` directory containing the `data*.rda` archives, not to the game installation root. Linux file systems are case-sensitive.

Running from source: `sudo apt install python3-tk`, `pip install -r requirements.txt`, then `python Anno_Island_Editor.py`.

## Detailed workflow

The recommended sequence is **configure → create/select a working island → unpack → edit → pack → export**. Keep source maps, working islands, and final exports in separate folders.

### 1. Configure Settings
Open **Settings** before starting. Configure the game folders and tools you need; the sections below explain each settings page. Use **Save settings** to persist the configuration. Browsed paths are also saved as they are selected.

### 2. Create or select a working island
On **Start**, choose **Create from Original Islands** or **Create from Custom Folder** to make a working copy, or select an existing `.a7m` file directly. Creating from a source copies the selected island under **Temporary Map Folder** and makes the copy active.

Select the desired unpack options, then click **Unpack island**. Wait for the operation to finish before editing.

### 3. Verify Files and Folders
Select the active `.a7m` on **Files and Folders**. The app attempts to detect the related `gamedata_original.xml`, `mapname_original.xml`, `rd3d_original.xml`, and TMC **Meshes folder**. Confirm that each path belongs to the same working island; browse to correct any missed path.

### 4. Set island and texture options
Use **Regional Settings** to choose regional values and a material set. Use **Texture Settings** if tint maps need adjustment. Saved tint-map presets can be selected and applied later.

### 5. Add and edit custom content
Use **Custom Content > Objects** to register custom object paths and **Custom Content > Slots** to define single Slots or River Slots. Configure the corresponding **Custom Objects Folder** and **Custom Material Sets Folder** in **Settings > Custom**. See [Custom Content](#custom-content) for how entries are saved and exported.

### 6. Edit objects and slots
Use **Object Configuration** and its Object Map for supported object edits. Use **Slot Configuration** and the Slot Map for slots. MapName and Gamedata changes are coordinated where required. Review validation feedback and save changes explicitly.

### 7. Pack and export
In **Finalize**, run **Pack Island Data** to rebuild the island's packed data from the available patched XML and changed TMC files. Then use **Export Island** to create a filtered copy in **Map Export Folder**. Export custom content and the Editor Mod Files separately when needed; neither button replaces packing or island export.

## Application areas

### Start / Files and Folders

These workflows select the island data used by the editor and provide the paths required by later operations.

On **Start**, select or create an island and choose which files to unpack. **Files and Folders** shows the active `.a7m`, its original XML files, and the TMC **Meshes folder**. Selecting an `.a7m` can auto-detect related files, but check that all paths point to the same working island before editing or packing.

### Settings

The Settings tab contains four pages. The configuration path is shown in the footer; settings are stored in `config.ini` beside the application.

#### General

- **Folder 'maindata'**: select the Anno 1800 `maindata` folder containing the game's `data*.rda` archives. This is used by the Helpers exports.
- **Folder 'mod'**: select the Anno 1800 `Mod` folder. **Finalize > Export Editor Mod Files** copies the bundled Island Editor mod here.
- **RdaConsole** and **FileDBReader**: required tools used for unpacking/packing game data. Bundled tools are detected automatically when available.
- **TMC parallel processes**: controls parallel TMC processing; the default is 4.
- **Validate paths** checks that the required tools and bundled XML formats are available. It does not validate every optional export folder.
- **Save settings** writes the current Settings options and refreshes the registered custom slot GUIDs.

#### Map Folders

Configure the source, working, and output folders described below. Keep these roles separate: source maps should not be used as the working or export destination.

#### Custom

- **Custom Material Sets Folder**: a folder of custom `.materialset` or XML material-set files. The Material Sets and Regional Settings tabs can load these files. **Export custom content files** includes all recognized material sets from this folder.
- **Custom Objects Folder**: the root folder containing the custom `.prp` files referenced by entries in **Custom Content > Objects**. Export preserves paths relative to this root.

#### Expert Settings

**Experimental** enables features explicitly marked experimental. River Slot placement is always available and is not controlled by this option.

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

**Used by:** **Start > Create from Original Islands**.

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

**Used by:** **Start > Create from Custom Folder**.

Use this when the source is not supposed to come from the indexed Original Maps tree. Typical examples are manually extracted islands, reusable base maps, maps from another modding workspace, or prepared source templates.

The chosen `.a7m` is **not edited in place**. It is used as the source for a new copy under Temporary Map Folder.

Do not confuse this with **Settings > Custom > Custom Objects Folder**. Custom Map Folder contains complete map sources; Custom Objects Folder contains custom `.prp` assets.

#### Temporary Map Folder
**Purpose:** destination for the editable working copies created from **Create from Original Islands** or **Create from Custom Folder**.

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
**Purpose:** root directory for the cleaned output from **Finalize > Export Island**.

This setting should point to a parent directory, not to a single map project. Export Island asks for the map name and creates:

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

Export Island is a **filtered release/output copy**, not another working-copy command. It excludes development artifacts, stages the complete export first, and only then replaces an existing destination after confirmation.

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
        | Create from Original Islands / Custom Folder, name: MyIsland
        v
Temporary Map Folder/MyIsland/MyIsland.a7m
        |
        | edit -> Save -> validate -> Pack Island Data
        v
Finalize > Export Island, name: MyIsland_Final
        |
        v
Map Export Folder/MyIsland_Final/MyIsland_Final.a7m
```

### Regional Settings

Use **Regional Settings** to compare original values with the values to be applied to the island. Regional conversion settings allow the island to be adapted between:

- Old World
- New World
- Enbesa
- Arctic

Regional conversion can affect multiple independent parts of an island, including material sets, object data, slots, and tintmaps.

The **Rivercolor** dropdown includes built-in values, **Original**, and **Custom**. Selecting **Custom** exposes a color preview; click it to choose a color or enter a decimal `WaterColor` value. The selected rivercolor is saved with the regional Gamedata settings.

### Texture Settings / Tintmaps

The tintmap workflow patches supported DDS tintmaps for a selected source and target region.

Set **From**, **To**, and **Brightness** in **Tint Map Settings**, then use **Patch Tintmaps**. **Custom** brightness accepts a whole-number offset from -255 to 255. The table below stores reusable settings with an optional comment:

- **Save Settings** adds the current From/To/Brightness/comment values.
- Select a row to load it into the controls. **Update Selected** replaces that row with the current values.
- **Delete Selected** removes the selected rows.

Presets are stored in `config_tintmap_presets.json` beside the application configuration. A suggested Old World-to-Enbesa preset is provided when no preset file exists.

Brightness modes include:

- **Normal**: regional conversion without an extra brightness offset
- **Brighter**: adds the configured positive RGB offset
- **Darker**: adds the configured negative RGB offset

The patcher uses backups and patch-state information to avoid unintentionally applying the same conversion repeatedly. If a tracked DDS file was changed externally, the application can report a conflict instead of silently overwriting it.

Tintmap processing may create an internal helper/cache directory named:

```text
_tintmap_variants/
```

This directory is used by the editing workflow and is **not included by Export Island**.

### Material Sets

The **Material Sets** tab can browse bundled material sets and the optional **Custom Material Sets Folder**. Open an `.xml` or `.materialset` file, edit its values, use **Reset** to discard unsaved edits, and **Save as...** to write a new material set without replacing the source.

Saving creates both a `.materialset` and its `.xml.lnk` companion. **Regional Settings** can select a material set for the island. **Finalize > Export custom content files** separately includes every recognized custom material set in the configured Custom Material Sets Folder.

### Custom Content

The **Custom Content** tab has two editors: **Objects** and **Slots**. User-defined entries are stored beside the application configuration and merged into the relevant object or slot workflows.

#### Objects

Each object entry has a **Region**, **Category**, and **Object** path. Use **Select Region** and **Select Category** to choose built-in or custom values, then **Add** or **Change** the table row. **Delete** removes selected rows. Click **Save** to write the table; unsaved edits are not persisted when the popup closes.

**Import .csv** can add or overwrite object rows and create missing custom region/category options. Review the import result and click **Save** to persist object rows. **Export .csv** writes the current table to a CSV file.

Object records and custom selection options are stored separately as `custom_objects.json` and `custom_object_options.json` beside the application configuration. The built-in object database is not modified.

#### Slots

Click **Slots** to manage both single Slots and River Slots. Choose **Slot Type** before adding an entry:

- **Slot** uses one positive numeric **GUID**.
- **River Slot** uses a positive numeric **GUID** and **GUID Work Area**.

Enter a unique name and GUID values, then click **Add**. Select a row and edit its fields to use **Change**. **Delete** removes selected entries; **Save** writes both slot lists and registers them with the Slot Editor. Duplicate names/GUIDs and built-in GUID conflicts are rejected.

Single Slots are saved in `config_custom_slots.json`; River Slots are saved in `config_custom_riverslots.json`. In the Slot Map, choose a configured single Slot from **Custom Slot** before right-clicking and choosing **Add Slot > Custom Slot**. Custom River Slot pairs appear in **River Slot Type**. The map legend uses configured single-slot names for their GUID labels.

#### Custom Objects Folder

The **Custom Objects Folder** contains the physical custom object files referenced by the custom object definitions.

When **Export custom content files** is used, the application does **not** blindly copy the entire Custom Objects Folder. It exports only registered custom objects that are actually referenced by the current island. The configured **Custom Material Sets Folder** is handled differently: all recognized material sets in that folder are included.

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

The Slot Map has a **River Slot Type** selector for built-in or configured River Slot pairs and a **Custom Slot** selector for configured single Slots. The latter is alphabetically sorted; when **Add Slot > Custom Slot** is chosen from the map's right-click menu, the selected slot's configured GUID is used. Configured single-slot names are shown in the map legend next to their GUIDs.

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

### Helpers

The **Helpers** tab extracts source files directly from the configured RDA archives. It is separate from **Finalize** exports:

- **Export material_sets** extracts `material_sets/` content from `data0.rda` through `data33.rda` into a folder you choose. Archives are processed in ascending order, so later archives can replace earlier files.
- **Export All Maps** extracts the `sessions\islands` content. **Create .lnk files for normal maps** controls whether normal-map textures are represented by links; the export also creates an A7M source CSV.
- **Export Custom** runs the configured RdaConsole filter from the **Custom** field. Enter the filter used by RdaConsole, then run the export.

These actions require a valid **Folder 'maindata'** and a working RdaConsole path in Settings.

### Validation and XML repair

The project contains dedicated validation and repair functionality for supported XML structures.

Validation is especially important when MapName and Gamedata references are changed. Do not ignore reported mismatches blindly. Review GUID, ObjectId, position, and slot-integration warnings before distributing an exported island.

## Finalize and Export

The **Finalize** tab contains separate actions. Run **Pack Island Data** before **Export Island** when XML edits need to be included in the exported island. Content exports below are separate and do not pack or export the island itself.

### CleanUp

**CleanUp** recursively deletes `.xml` and `.data` files, files whose names contain `_original` or `_backup`, and common backup files from the active island root. It does not remove directories. **This is destructive and cannot be undone.** Use it only after packing/exporting and only when you no longer need the working XML or backups.

### Pack Island Data

**Pack Island Data** rebuilds the active island's packed data from available patched XML (falling back to original XML when a patched file is missing), repacks changed TMC files from the **Meshes folder**, installs the resulting binary data, and repacks the `.a7m`. If a patched A7MINFO XML exists, it is also rebuilt. Existing binaries are backed up when **Back up existing binary files** is enabled.

The active `.a7m`, its unpacked data folder, the Meshes folder, RdaConsole, and FileDBReader must be available. Review the Finalize log and any warnings before continuing.

### Export Island

**Export Island** creates a filtered copy of the active map directory under `<Map Export Folder>/<Map Name>`. The current `.a7m` name is offered as the default; you may enter a different output name. The exporter renames matching map-owned files/folders and stages the copy before replacing an existing destination after confirmation.

It copies existing files only; **it does not pack XML edits**. Run **Pack Island Data** first when needed. The export excludes `.xml`, `.data`, `.json`, original/backup artifacts, and `_tintmap_variants`. `.xml.lnk` files are retained. The source and destination must be separate, non-overlapping folders.

### Export custom content files

This button asks for an export destination and includes:

- Only registered custom object files referenced by the active island, placed under `custom_objects/` with their path relative to **Custom Objects Folder** preserved.
- Every `.materialset` or `.xml` material set in **Settings > Custom > Custom Material Sets Folder**, placed under `data/config/engine/material_sets/` with a matching `.xml.lnk` companion. If both extensions exist for the same name, `.materialset` takes precedence.

This export does not include the bundled Editor Mod Files or custom River Slot configuration files.

### Export Editor Mod Files

**Export Editor Mod Files** copies the bundled `[IslandEditor] ModFiles [gz2k2]` package into the configured Anno 1800 **Mod** folder. It includes the editor's required mod content, including bundled material sets and integrated River Slot files. Configure **Settings > General > Folder 'mod'** first. Existing files are listed for overwrite confirmation.

### Stop immediately

This button is enabled while a long operation is running. Use it to request cancellation; wait for the status window and log to confirm the operation has stopped before closing the app or changing files.

## Troubleshooting

- **Validate paths** reports missing RdaConsole, FileDBReader, or bundled XML format files. Correct these in **Settings > General**. Optional map/export folders are configured separately.
- **Pack Island Data** requires an active `.a7m`, its unpacked data folder, and the matching Meshes folder. Check **Files and Folders** if packing reports a missing source.
- **Export Island** requires **Map Export Folder** and cannot write inside or over the active source map. Choose a separate output root in **Settings > Map Folders**.
- **Export custom content files** reports missing `.prp` files when a referenced custom object cannot be found under **Custom Objects Folder**. Check the object path in **Custom Content > Objects** and the folder in **Settings > Custom**.
- **Export Editor Mod Files** requires an existing Anno 1800 **Mod** folder configured under **Settings > General**. Confirm the overwrite prompt to replace files from an earlier copy.
- A configured single Slot is available in the Slot Map's **Custom Slot** dropdown after it is saved in **Custom Content > Slots**. If the list is empty or disabled, add and save a Slot first.

## Project structure

Key application files and packages:

```text
Anno_Island_Editor.py
00_build_onefile.py
version.txt

app/
├── main.py
├── backend/
│   └── backend_xml.py
├── config/
│   ├── config_colors.py
│   ├── config_gamedata.py
│   ├── config_rd3d.py
│   └── config_slot.py
├── database/
│   └── database_props.py
├── functions/
│   ├── function_custom_content.py
│   ├── function_custom_slots.py
│   ├── function_custom_river_slots.py
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

tests/  (automated tests; not required by the application at runtime)
```

Each Python package directory contains its own `__init__.py`.

## Running from source

A Python environment with the application's dependencies is required. The GUI uses CustomTkinter/Pillow and the current XML backend uses lxml.

Install the requirements from the project root, then start the application with:

```bash
python -m pip install -r requirements.txt
python Anno_Island_Editor.py
```

For development, run tests from the project root with:

```bash
python -m pytest
```

## Building the executable

The repository contains:

```text
00_build_onefile.py
```

It validates the expected project/package structure and builds a PyInstaller one-file application for the operating system on which it is run. Build on the target operating system; PyInstaller does not cross-compile Windows and Linux executables.

Run:

```bash
python 00_build_onefile.py
```

The application version is read from:

```text
version.txt
```

The output name follows `APP_NAME_BASE` and the version in `version.txt`. For example, with version `0.120.12`, the Windows executable is named:

```text
Anno_Island_Skin_and_Slot_Editor_v0.120.12.exe
```

The build is written to the `dist/` directory.

The `tests/` package is intentionally excluded from the application executable.

## GitHub releases

The GitHub Actions release workflow uses `version.txt` as the release version and calls the same `00_build_onefile.py` builder used for local builds.

For a tagged release, the Git tag should match the version in `version.txt`:

```text
version.txt: 0.120.12
Git tag:     v0.120.12
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

When application behavior changes, update the usage instructions and verify that menu names and workflow descriptions still match the UI.

## Support

If the tool is useful to you and you want to support continued development:

**Ko-fi:** [http://www.ko-fi.com/gz2k2](http://www.ko-fi.com/gz2k2)
