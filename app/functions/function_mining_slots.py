"""Specialized MineSlot placement methods extracted from function_island_slots."""

from app.functions.function_island_slots import *  # noqa: F401,F403


class MiningSlotEditingMixin:
    # ---------------------------------------------------------------------
    # Selectable MineSlot variants
    # ---------------------------------------------------------------------
    # Tuple entries are: (label shown in the UI, GUID written to Gamedata).
    # All variants are generated from the verified native 1000029 template;
    # only the final GUID changes after the shared MineSlot setup is complete.
    MINE_SLOT_VARIANTS = (
        ("MineSlot (OW, NW Gold)", "1000029"),
        ("MineSlot (NW)", "614"),
        ("MineSlot (Arctic)", "116037"),
    )

    # Allowed horizontal distance, in world units, between the first click
    # (MineSlot) and the second click (outer Work Area 1000253). Placements
    # outside this range are rejected before any XML objects are generated.
    MINE_MIN_DISTANCE = 2.0
    MINE_MAX_DISTANCE = 20.0

    # ---------------------------------------------------------------------
    # Inner Work Area / Cave object 100419
    # ---------------------------------------------------------------------
    # Preferred forward distance, in world units, from the MineSlot toward the
    # outer Work Area. Native examples place 100419 about five units away.
    MINE_CAVE_ALONG_DISTANCE = 5.08

    # Lower and upper limits for the relative 100419 position along the full
    # MineSlot -> outer Work Area distance. Example: 0.25 means 25 percent.
    # These limits keep 100419 usable when the selected total distance is much
    # shorter or longer than the preferred MINE_CAVE_ALONG_DISTANCE.
    MINE_CAVE_MIN_FRACTION = 0.25
    MINE_CAVE_MAX_FRACTION = 0.60

    # Horizontal sideways displacement of 100419 from the direct MineSlot ->
    # Work Area line, in world units. Both sides are tested against the
    # HeightMap; the candidate on the higher valid rock surface is selected.
    MINE_CAVE_LATERAL_OFFSET = 1.17

    # Multiplier applied only to the calculated absolute Y position of 100419.
    # 1.0 keeps the HeightMap result, 1.05 raises it by five percent, and 0.95
    # lowers it by five percent. Normally leave this at 1.0 because an additive
    # object offset is available through MINE_WORKAREAS_HEIGHT_OFFSET below.
    MINE_CAVE_HEIGHT_MULTIPLIER = 1.0

    # ---------------------------------------------------------------------
    # Generated Mining BezierPaths for 100419 and 1000253
    # ---------------------------------------------------------------------
    # Mandatory vertical clearance, in world-height units, between the highest
    # sampled HeightMap surface and the generated rail/path centerline. This is
    # the technical safety distance that prevents rails from entering rock.
    MINE_PATH_CLEARANCE = 0.40

    # Additional user-tuning offset, in world-height units, for both generated
    # Mining BezierPaths. Positive values raise all path points; negative values
    # lower them. This is added after HeightMap sampling and PATH_CLEARANCE.
    MINE_PATH_HEIGHT_OFFSET = 0.2

    # Radius, in horizontal world units, around every Bezier point used for its
    # HeightMap footprint check. The center, four cardinal directions and four
    # diagonals are sampled; the highest result is used. A larger value protects
    # wider rails from nearby rock but can lift paths beside steep cliffs.
    MINE_PATH_FOOTPRINT_RADIUS = 0.45

    # ---------------------------------------------------------------------
    # Generated object positions (not BezierPath points)
    # ---------------------------------------------------------------------
    # Additive Y offset, in world-height units, for the actual MineSlot object
    # (selected GUID 1000029, 614 or 116037). It does not change path clearance.
    MINE_SLOT_HEIGHT_OFFSET = 0.1

    # Shared additive Y offset, in world-height units, for both Work Area
    # objects: outer Work Area 1000253 and inner Cave/Work Area 100419.
    # It changes the object anchors, but MINE_PATH_HEIGHT_OFFSET independently
    # controls the generated rail/path elevation.
    MINE_WORKAREAS_HEIGHT_OFFSET = 5.0

    def _mine_path_surface_height(self, x, z, samples):
        """Return the highest bilinear HeightMap sample below the rail footprint."""
        radius = self.MINE_PATH_FOOTPRINT_RADIUS
        offsets = (
            (0.0, 0.0), (radius, 0.0), (-radius, 0.0),
            (0.0, radius), (0.0, -radius),
            (radius, radius), (radius, -radius),
            (-radius, radius), (-radius, -radius),
        )
        heights = [
            self._river_terrain_height(x + dx, z + dz, samples)
            for dx, dz in offsets
        ]
        heights = [height for height in heights if height is not None]
        return max(heights) if heights else None
    def _island_slot_add_mineslot_at_event(self, event, display_name, guid):
        """Start two-click mine placement; do not change XML yet."""
        self._island_slot_cancel_mine_placement(silent=True)
        x, z = self._island_slot_world(event)
        x, z = math.floor(x) + 0.5, math.floor(z) + 0.5
        samples, source = self._island_slot_height_samples()
        y = self._river_terrain_height(x, z, samples)
        if y is None or y <= 0:
            messagebox.showerror(
                "Add Mine Slot", "Mine entrance must be placed on emerged terrain.",
                parent=self.slot_map_window)
            return
        self._mine_placement = {
            "kind": "mine", "name": display_name, "guid": str(guid),
            "entrance": (x, y, z), "samples": samples, "source": source,
        }
        self.slot_map_allow_dot_movement_var.set(False)
        self._slot_map_dot_movement_changed()
        self.slot_map_canvas.focus_set()
        self.status_var.set(
            f"Mine entrance selected at X/Z {x:g} / {z:g}. "
            "Left-click to place the Work Area; right-click or Esc to cancel.")
        self._island_slot_draw_mine_preview(None)

    def _island_slot_commit_mine_pair(self, placement, entrance, mountain, status):
        """Atomically generate Mine, Work Area and a nine-point terrain path."""
        go, mo, gp, mp = self._island_slot_sources()
        if self._island_slot_ram_game_tree is None or self._island_slot_ram_map_tree is None:
            self._island_slot_ram_game_tree = self._slot_parse_xml(gp if gp.is_file() else go)[0]
            self._island_slot_ram_map_tree = self._slot_parse_xml(mp if mp.is_file() else mo)[0]
        game_tree, map_tree = deepcopy(self._island_slot_ram_game_tree), deepcopy(self._island_slot_ram_map_tree)
        game_root, map_root = game_tree.getroot(), map_tree.getroot()
        records = object_records(game_root); container = game_object_container(game_root)
        target_guid = str(placement["guid"])
        if target_guid not in MINE_SLOT_GUIDS:
            raise ValueError(f"Unsupported MineSlot GUID: {target_guid}")
        # Master logic: every variant starts as the verified native 1000029
        # MineSlot. Only after the complete master object has been configured is
        # its GUID changed to the selected target variant. This guarantees that
        # 614 and 116037 inherit exactly the tested master structure, Direction
        # and Mesh/Orientation instead of cloning unrelated island objects.
        mine = template_element(MINE_TEMPLATE_NAME)
        if text(mine, "guid") != MINE_MASTER_GUID:
            raise ValueError("MineSlot master template GUID is not 1000029.")
        workarea = template_element(MINE_WORKAREA_TEMPLATE_NAME)
        if text(workarea, "guid") != MINE_WORKAREA_GUID:
            raise ValueError("MineSlot Work Area template GUID is not 1000253.")
        cave = template_element(MINE_CAVE_TEMPLATE_NAME)
        if text(cave, "guid") != MINE_CAVE_GUID:
            raise ValueError("MineSlot Cave template GUID is not 100419.")
        used = all_ids(map_root, game_root)
        # Work Area, Mine and Cave are one native logical family.
        mine_id, work_id, cave_id = allocate_verified_id_family(
            map_root, game_root, used, 3)
        folder = new_folder_id(records)
        mine_position = (
            entrance[0], entrance[1] + self.MINE_SLOT_HEIGHT_OFFSET, entrance[2])
        workarea_position = (
            mountain[0], mountain[1] + self.MINE_WORKAREAS_HEIGHT_OFFSET, mountain[2])
        for node, oid, guid, position in (
            (mine, mine_id, target_guid, mine_position),
            (workarea, work_id, MINE_WORKAREA_GUID, workarea_position),
        ):
            set_text(node,"ID",oid); set_text(node,"Position",format_position(position))
            guid_node=direct(node,"guid"); guid_node.text=guid
            folder_node=direct(node,"ObjectFolderID")
            if folder_node is None:
                folder_node=ET.Element("ObjectFolderID"); node.insert(2,folder_node)
            folder_node.text=folder
        # Place Cave 100419 from native corpus geometry. Its center is about
        # five units from the MineSlot and normally offset sideways. Native
        # examples use both sides, so evaluate both candidates against the
        # HeightMap and choose the higher rock surface.
        original_cave_position = parse_position(text(cave, "Position"))
        original_master_direction = math.pi
        axis_x = mountain[0] - entrance[0]
        axis_z = mountain[2] - entrance[2]
        axis_length = math.hypot(axis_x, axis_z)
        if axis_length <= 0.000001:
            raise ValueError("Mine and Work Area positions are identical.")
        unit_x, unit_z = axis_x / axis_length, axis_z / axis_length
        cave_fraction = max(
            self.MINE_CAVE_MIN_FRACTION,
            min(self.MINE_CAVE_MAX_FRACTION,
                self.MINE_CAVE_ALONG_DISTANCE / axis_length),
        )
        center_x = entrance[0] + axis_x * cave_fraction
        center_z = entrance[2] + axis_z * cave_fraction
        normal_x, normal_z = -unit_z, unit_x
        candidates = []
        for side in (-1.0, 1.0):
            candidate_x = center_x + normal_x * self.MINE_CAVE_LATERAL_OFFSET * side
            candidate_z = center_z + normal_z * self.MINE_CAVE_LATERAL_OFFSET * side
            candidate_y = self._river_terrain_height(
                candidate_x, candidate_z, placement["samples"])
            if candidate_y is not None and candidate_y > 0:
                candidates.append((candidate_y, candidate_x, candidate_z))
        if candidates:
            midpoint_y, midpoint_x, midpoint_z = max(candidates)
        else:
            midpoint_x, midpoint_z = center_x, center_z
            midpoint_y = self._river_terrain_height(
                midpoint_x, midpoint_z, placement["samples"])
            if midpoint_y is None or midpoint_y <= 0:
                midpoint_y = entrance[1] + (mountain[1] - entrance[1]) * cave_fraction
        midpoint_y *= self.MINE_CAVE_HEIGHT_MULTIPLIER
        cave_midpoint = (
            midpoint_x,
            midpoint_y + self.MINE_WORKAREAS_HEIGHT_OFFSET,
            midpoint_z,
        )
        set_text(cave, "ID", cave_id)
        set_text(cave, "ObjectFolderID", folder)
        target_cave_rotation = (-math.atan2(
            mountain[0] - entrance[0], mountain[2] - entrance[2]
        ) + math.pi / 2.0) % (2.0 * math.pi)
        rotation_delta = math.degrees(
            target_cave_rotation - original_master_direction)
        rotate_clone_y(cave, original_cave_position, rotation_delta)
        dx = cave_midpoint[0] - original_cave_position[0]
        dz = cave_midpoint[2] - original_cave_position[2]
        relocate_clone(
            cave, dx, dz,
            lambda x, z: (
                (surface + self.MINE_PATH_CLEARANCE + self.MINE_PATH_HEIGHT_OFFSET)
                if (surface := self._mine_path_surface_height(
                    x, z, placement["samples"])) is not None else None
            ),
        )
        # relocate_clone follows terrain for every path point. Set the Cave's
        # object anchor explicitly to the exact requested midpoint afterwards.
        set_text(cave, "Position", format_position(cave_midpoint))

        direction = math.atan2(
            mountain[0] - entrance[0],
            mountain[2] - entrance[2],
        )
        # Mesh/Orientation controls the correctly aligned unbuilt mine graphic
        # and is handled separately below. The constructed 1000029 building uses
        # Direction with a +90-degree asset offset, but its horizontal X axis is
        # mirrored: up/down are correct while left/right must be exchanged.
        # All three variants are configured as 1000029 master objects before
        # the GUID swap, so all three use the same verified master Direction.
        mine_direction = (-direction + math.pi / 2.0) % (2.0 * math.pi)
        for node, node_direction in (
            (mine, mine_direction),
            (workarea, direction),
        ):
            dn = direct(node, "Direction")
            if dn is None:
                dn = ET.Element("Direction")
                pos = direct(node, "Position")
                node.insert(list(node).index(pos) + 1, dn)
            dn.text = game_number(node_direction)

        # Direction and the Slot Map arrow are already correct. Do not rotate
        # the cloned quaternion relatively. Build the MineSlot yaw quaternion
        # directly from that Direction. Native 1000029 uses yaw = -Direction
        # (for example Direction +PI/2 corresponds to Orientation Y -0.7071).
        mesh = direct(mine, "Mesh")
        orientation = direct(mesh, "Orientation") if mesh is not None else None
        if orientation is None:
            raise ValueError("MineSlot master template has no Mesh/Orientation.")
        # Runtime facing swaps the map's X/Z angle basis. Convert the
        # already-correct Mine -> Work Area direction by reflecting the angle
        # across the X/Z diagonal: up->up, right->right, left->left, down->down.
        orientation_direction = math.pi / 2.0 - direction
        half_yaw = orientation_direction / 2.0
        orientation.text = " ".join(game_number(value) for value in (
            0.0,
            -math.sin(half_yaw),
            0.0,
            math.cos(half_yaw),
        ))
        # Keep the native nine-point Mine Work Area curve, but store it in
        # local coordinates relative to the Work Area. This mirrors the
        # verified custom River Work Area format: p=0/0/0 at the Work Area and
        # the final point reaches the MineSlot with a relative height delta.
        curve = next((node for node in workarea.iter()
                      if tag(node) == "BezierCurve"), None)
        if curve is None or len(curve) < 2:
            raise ValueError("Work Area template has no usable BezierCurve.")
        template_items = list(curve)
        template_points = [parse_position(text(item, "p"))
                           for item in template_items]
        source_start, source_end = template_points[0], template_points[-1]
        source_dx = source_end[0] - source_start[0]
        source_dz = source_end[2] - source_start[2]
        source_length = math.hypot(source_dx, source_dz)
        target_dx = entrance[0] - mountain[0]
        target_dz = entrance[2] - mountain[2]
        target_length = math.hypot(target_dx, target_dz)
        if source_length <= 0.000001 or target_length <= 0.000001:
            raise ValueError("Mine Work Area BezierPath has zero length.")
        source_angle = math.atan2(source_dz, source_dx)
        target_angle = math.atan2(target_dz, target_dx)
        rotation = target_angle - source_angle
        cosine, sine = math.cos(rotation), math.sin(rotation)
        scale = target_length / source_length
        height_delta = entrance[1] - mountain[1]

        def transform_local_xz(x_value, z_value):
            scaled_x, scaled_z = x_value * scale, z_value * scale
            return (scaled_x * cosine - scaled_z * sine,
                    scaled_x * sine + scaled_z * cosine)

        local_points = []
        new_items = []
        count = len(template_items)
        for index, (item, source_point) in enumerate(
                zip(template_items, template_points)):
            relative_x = source_point[0] - source_start[0]
            relative_z = source_point[2] - source_start[2]
            local_x, local_z = transform_local_xz(relative_x, relative_z)

            # Use the same local-coordinate convention as RiverSlots, but
            # derive every Mine path point from the real HeightMap. This keeps
            # the connector on the rock surface instead of cutting through it.
            world_x = mountain[0] + local_x
            world_z = mountain[2] + local_z
            terrain_y = self._mine_path_surface_height(
                world_x, world_z, placement["samples"])
            if terrain_y is None:
                progress = index / (count - 1)
                terrain_y = mountain[1] + height_delta * progress
            # The Bezier points represent the rail centerline, not bare ground.
            # Keep the complete footprint above the highest nearby terrain.
            local_y = terrain_y + self.MINE_PATH_CLEARANCE + self.MINE_PATH_HEIGHT_OFFSET - mountain[1]
            point = (local_x, local_y, local_z)
            local_points.append(point)

            replacement = ET.Element("None")
            ET.SubElement(replacement, "p").text = format_position(point)
            for tangent_name in ("i", "o"):
                tangent = parse_position(text(item, tangent_name))
                tangent_x, tangent_z = transform_local_xz(
                    tangent[0], tangent[2])
                # Native Y tangents belong to the source mountain profile and
                # can pull the cubic segment below the target HeightMap. Keep
                # horizontal curvature, but make vertical interpolation monotone.
                tangent_value = (tangent_x, 0.0, tangent_z)
                ET.SubElement(replacement, tangent_name).text = format_position(
                    tangent_value)
            new_items.append(replacement)

        # Preserve exact X/Z anchors, but never force Y back to the object
        # anchors: those are terrain-level and made the first/last rail pieces
        # intersect the rock. Re-sample both complete rail footprints instead.
        endpoint_specs = (
            (0, mountain[0], mountain[2], 0.0, 0.0),
            (-1, entrance[0], entrance[2], target_dx, target_dz),
        )
        for item_index, world_x, world_z, local_x, local_z in endpoint_specs:
            surface = self._mine_path_surface_height(
                world_x, world_z, placement["samples"])
            if surface is None:
                surface = mountain[1] if item_index == 0 else entrance[1]
            point = (local_x,
                     surface + self.MINE_PATH_CLEARANCE + self.MINE_PATH_HEIGHT_OFFSET - mountain[1],
                     local_z)
            local_points[item_index] = point
            direct(new_items[item_index], "p").text = format_position(point)
        for child in list(curve):
            curve.remove(child)
        for item in new_items:
            curve.append(item)

        path = curve.getparent()
        minimum, maximum = direct(path, "Minimum"), direct(path, "Maximum")
        if minimum is None or maximum is None:
            raise ValueError("Mine Work Area template lacks Bezier bounds.")
        minimum.text = format_position(tuple(
            min(point[axis] for point in local_points) for axis in range(3)))
        maximum.text = format_position(tuple(
            max(point[axis] for point in local_points) for axis in range(3)))
        StatusWindowTemplate.update(status,fraction=.7)
        append_pretty(container,mine); append_pretty(container,workarea); append_pretty(container,cave)
        append_map_entry(map_root,MINE_PRIMARY_GROUP,mine_id,target_guid,format_position(mine_position))
        append_map_entry(map_root,MINE_WORKAREA_GROUP,work_id,MINE_WORKAREA_GUID,format_position(workarea_position))
        append_map_entry(map_root,MINE_CAVE_GROUP,cave_id,MINE_CAVE_GUID,text(cave, "Position"))
        group_name = append_mine_object_group(game_root, work_id, mine_id, cave_id)
        validate_pair(map_root,game_root)
        self._island_slot_ram_game_tree,self._island_slot_ram_map_tree=game_tree,map_tree
        StatusWindowTemplate.update(status,fraction=1)
        self.status_var.set(f"Added {placement['name']} from master {MINE_MASTER_GUID} as GUID {target_guid} with Work Area | IDs: {mine_id}, {work_id} | Folder: {folder}")
        self._refresh_open_slot_map()
