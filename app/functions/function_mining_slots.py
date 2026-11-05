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

    # MineSlot assets use a raster-aligned facing in the native data. Snap only
    # the MineSlot visual/Direction to this increment; the Work Area and its
    # BezierPath still follow the exact two-click vector. Set to 0 to disable.
    # Placement/orientation snap in degrees. Useful test values: 15.0, 30.0, 45.0.
    # Set <= 0 to disable angular snapping.
    MINE_ORIENTATION_SNAP_DEGREES = 90.0
    # Optional fine adjustment after deriving 1000253 orientation from the
    # direct Work Area -> MineSlot axis. Terrain curvature must not rotate it.
    MINE_WORKAREA_PATH_DIRECTION_OFFSET_DEGREES = 0.0
    # Radius of the MineSlot placement helper circle in world-coordinate units.
    MINE_PLACEMENT_CIRCLE_RADIUS = 2.5

    # Native 1000253 paths do not run from object-center to object-center.
    # The Work Area end starts ~0.6158 world units behind its object anchor,
    # while the MineSlot end stops 0.5 world units in front of the MineSlot.
    # These values are visible consistently in the original slots of the map.
    MINE_PATH_WORKAREA_ANCHOR_OFFSET = 0.6158
    MINE_PATH_MINESLOT_ANCHOR_OFFSET = 0.5

    # Native 100419 curves start roughly 1.34 horizontal world units outside
    # the 100419 object anchor, on the side away from the MineSlot.
    MINE_CAVE_PATH_START_OFFSET = 1.34

    # ---------------------------------------------------------------------
    # Inner Work Area / Cave object 100419
    # ---------------------------------------------------------------------
    # Preferred forward distance, in world units, from the MineSlot toward the
    # outer Work Area. Native examples place 100419 about five units away.
    MINE_CAVE_ALONG_DISTANCE = 5.0

    # Lower and upper limits for the relative 100419 position along the full
    # MineSlot -> outer Work Area distance. Example: 0.25 means 25 percent.
    # These limits keep 100419 usable when the selected total distance is much
    # shorter or longer than the preferred MINE_CAVE_ALONG_DISTANCE.
    MINE_CAVE_MIN_FRACTION = 0.25
    MINE_CAVE_MAX_FRACTION = 0.60

    # Horizontal sideways displacement of 100419 from the direct MineSlot ->
    # Work Area line, in world units. Both sides are tested against the
    # HeightMap; the candidate on the higher valid rock surface is selected.
    MINE_CAVE_LATERAL_OFFSET = 1.15

    # Multiplier applied only to the calculated absolute Y position of 100419.
    # 1.0 keeps the HeightMap result, 1.05 raises it by five percent, and 0.95
    # lowers it by five percent. Normally leave this at 1.0; the separate
    # additive object offset is controlled by MINE_CAVE_HEIGHT_OFFSET.
    MINE_CAVE_HEIGHT_MULTIPLIER = 1.0
    # Additive Y offset, in world-height units, for the inner Cave/Work Area
    # object 100419. This can be tuned independently from outer Work Area 1000253.
    MINE_CAVE_HEIGHT_OFFSET = 0.1

    # ---------------------------------------------------------------------
    # Generated Mining BezierPaths for 100419 and 1000253
    # ---------------------------------------------------------------------
    # Mandatory vertical clearance, in world-height units, between the highest
    # sampled HeightMap surface and the generated rail/path centerline. This is
    # the technical safety distance that prevents rails from entering rock.
    MINE_PATH_CLEARANCE = 0.40

    # Additional user-tuning offset, in world-height units, for HeightMap-based
    # Mining BezierPath control points. Object-anchored Work Area endpoints use
    # their own offsets below.
    MINE_PATH_HEIGHT_OFFSET = 0.2

    # Extra Y offsets, in world-height units, for the Work Area Bezier endpoints.
    # Zero keeps each endpoint exactly level with its corresponding object.
    MINE_PATH_MINESLOT_HEIGHT_OFFSET = 0.0
    MINE_PATH_WORKAREA_HEIGHT_OFFSET = 0.0

    # Additional lift, in world-height units, for interior Mine Bezier control
    # points. The endpoints are pinned separately to their object heights.
    MINE_PATH_EXTRA_LIFT = 0.3

    # Radius, in horizontal world units, around every Bezier point used for its
    # HeightMap footprint check. The center, four cardinal directions and four
    # diagonals are sampled; the highest result is used. A larger value protects
    # wider rails from nearby rock but can lift paths beside steep cliffs.
    MINE_PATH_FOOTPRINT_RADIUS = 0.45

    # Adaptive Bezier density calibrated against 185 native mine packages.
    # Distance supplies the base density; terrain variation adds detail.
    MINE_PATH_DISTANCE_STEP = 1.75
    MINE_PATH_ROUGHNESS_HEIGHT = 0.75
    MINE_CAVE_PATH_MIN_POINTS = 2
    MINE_CAVE_PATH_MAX_POINTS = 8
    MINE_WORKAREA_PATH_MIN_POINTS = 5
    MINE_WORKAREA_PATH_MAX_POINTS = 13
    MINE_PATH_PROFILE_SAMPLES = 33
    # Restrained native-style outer path geometry.
    MINE_WORKAREA_PATH_POINTS = 9
    MINE_PATH_MAX_LATERAL_OFFSET = 0.35
    MINE_PATH_MAX_HANDLE_LENGTH = 0.90

    # ---------------------------------------------------------------------
    # Generated object positions (not BezierPath points)
    # ---------------------------------------------------------------------
    # Additive Y offset, in world-height units, for the actual MineSlot object
    # (selected GUID 1000029, 614 or 116037). It does not change path clearance.
    MINE_SLOT_HEIGHT_OFFSET = 0.1

    # Additive Y offset, in world-height units, for outer Work Area 1000253.
    # It does not change generated rail elevation, which is controlled by
    # MINE_PATH_HEIGHT_OFFSET.
    MINE_WORKAREA_HEIGHT_OFFSET = 0.4

    def mine_workarea_path_endpoints(
            self, mine_position, workarea_position,
            mine_path_anchor, workarea_path_anchor):
        """Return MineSlot-to-Work-Area Bezier endpoints at object-relative heights."""
        return (
            (
                mine_path_anchor[0],
                mine_position[1] + self.MINE_PATH_MINESLOT_HEIGHT_OFFSET,
                mine_path_anchor[1],
            ),
            (
                workarea_path_anchor[0],
                workarea_position[1] + self.MINE_PATH_WORKAREA_HEIGHT_OFFSET,
                workarea_path_anchor[1],
            ),
        )

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
        """Enter free two-click MineSlot placement; the menu click is not a placement click."""
        self._island_slot_cancel_mine_placement(silent=True)
        samples, source = self._island_slot_height_samples()
        self._mine_placement = {
            "kind": "mine", "name": display_name, "guid": str(guid),
            "entrance": None, "samples": samples, "source": source,
        }
        self.slot_map_allow_dot_movement_var.set(False)
        self._slot_map_dot_movement_changed()
        self.slot_map_canvas.focus_set()
        self.status_var.set(
            "Move the mouse and left-click to place the Mine entrance; "
            "right-click or Esc to cancel.")
        self._island_slot_draw_mine_preview(event)

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
        # Generated Mine, Work Area and Cave objects use the neutral runtime folder,
        # matching Island Editor's proven Gamedata integration.
        folder = "0"
        mine_position = (
            entrance[0], entrance[1] + self.MINE_SLOT_HEIGHT_OFFSET, entrance[2])
        workarea_position = (
            mountain[0], mountain[1] + self.MINE_WORKAREA_HEIGHT_OFFSET, mountain[2])
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
            midpoint_y + self.MINE_CAVE_HEIGHT_OFFSET,
            midpoint_z,
        )
        set_text(cave, "ID", cave_id)
        set_text(cave, "ObjectFolderID", folder)
        set_text(cave, "Position", format_position(cave_midpoint))

        # Templates contain captured runtime animation timestamps. New objects must
        # start in a neutral sequence state, as done by Island Editor.
        for runtime_node in (mine, workarea, cave):
            mesh = direct(runtime_node, "Mesh")
            sequence = direct(mesh, "SequenceData") if mesh is not None else None
            start = direct(sequence, "CurrentSequenceStartTime") if sequence is not None else None
            if start is None:
                raise ValueError(
                    f"Generated slot object {text(runtime_node, 'guid')} lacks "
                    "Mesh/SequenceData/CurrentSequenceStartTime."
                )
            start.text = "0"
        # 100419 path geometry is generated only after the shared MineSlot
        # connector has been calculated. Do not rotate/relocate its clone: that
        # used the template pivot and separated the path from the object anchor.

        direction = math.atan2(
            mountain[0] - entrance[0],
            mountain[2] - entrance[2],
        )
        # MineSlot and Work Area use one shared 45-degree placement axis.
        # The second placement point is snapped before commit, so both objects
        # and the connector path are derived from the same exact direction.
        mine_direction = direction % (2.0 * math.pi)
        snap_degrees = float(self.MINE_ORIENTATION_SNAP_DEGREES)
        if snap_degrees > 0.0:
            snap_radians = math.radians(snap_degrees)
            mine_direction = (
                round(mine_direction / snap_radians) * snap_radians
            ) % (2.0 * math.pi)
        # 1000029 uses its raster-snapped facing. 1000253 is intentionally
        # excluded here: its final Direction is derived from the native template
        # after build_mining_curve has calculated the real path rotation.
        mine_direction_node = direct(mine, "Direction")
        if mine_direction_node is None:
            mine_direction_node = ET.Element("Direction")
            mine_position_node = direct(mine, "Position")
            mine.insert(list(mine).index(mine_position_node) + 1,
                        mine_direction_node)
        mine_object_direction = (mine_direction + (math.pi / 2.0)) % (2.0 * math.pi)
        # Native 1000029 has the opposite facing on the horizontal X placement
        # axis. Keep vertical cases unchanged and do not touch Work Area 1000253.
        placement_dx = mountain[0] - entrance[0]
        placement_dz = mountain[2] - entrance[2]
        if abs(placement_dx) > abs(placement_dz):
            mine_object_direction = (mine_object_direction + math.pi) % (2.0 * math.pi)
        mine_direction_node.text = game_number(mine_object_direction)

        # Native MineSlot direction equals the snapped placement/path axis. Do not rotate
        # the cloned quaternion relatively. Build the MineSlot yaw quaternion
        # directly from that Direction. Native 1000029 uses yaw = -Direction
        # (for example Direction +PI/2 corresponds to Orientation Y -0.7071).
        mesh = direct(mine, "Mesh")
        orientation = direct(mesh, "Orientation") if mesh is not None else None
        if orientation is None:
            raise ValueError("MineSlot master template has no Mesh/Orientation.")
        # Build the quaternion from the same snapped Direction written above.
        # This prevents Direction and Mesh/Orientation from representing two
        # different facings when the click vector is not axis-aligned.
        half_yaw = mine_object_direction / 2.0
        orientation.text = " ".join(game_number(value) for value in (
            0.0,
            -math.sin(half_yaw),
            0.0,
            math.cos(half_yaw),
        ))
        # Native mine paths use connector anchors rather than the centers of
        # 1000253 and 1000029.  Start slightly behind the Work Area and stop
        # half a unit before the MineSlot.  The MineSlot side follows its
        # raster-snapped facing, matching the original game's +/-0.5 X/Z ends.
        axis_to_mine_x = entrance[0] - mountain[0]
        axis_to_mine_z = entrance[2] - mountain[2]
        axis_to_mine_length = math.hypot(axis_to_mine_x, axis_to_mine_z)
        if axis_to_mine_length <= 0.000001:
            raise ValueError("Mine Work Area BezierPath has zero length.")
        axis_unit_x = axis_to_mine_x / axis_to_mine_length
        axis_unit_z = axis_to_mine_z / axis_to_mine_length
        workarea_path_anchor = (
            mountain[0] - axis_unit_x * self.MINE_PATH_WORKAREA_ANCHOR_OFFSET,
            mountain[2] - axis_unit_z * self.MINE_PATH_WORKAREA_ANCHOR_OFFSET,
        )
        # Select the cardinal direction which points from MineSlot toward the
        # Work Area. This reproduces the native 0.5-unit connector offset even
        # when the user's second click is not perfectly axis-aligned.
        toward_work_x = mountain[0] - entrance[0]
        toward_work_z = mountain[2] - entrance[2]
        if abs(toward_work_x) >= abs(toward_work_z):
            mine_connector_x = math.copysign(self.MINE_PATH_MINESLOT_ANCHOR_OFFSET, toward_work_x)
            mine_connector_z = 0.0
        else:
            mine_connector_x = 0.0
            mine_connector_z = math.copysign(self.MINE_PATH_MINESLOT_ANCHOR_OFFSET, toward_work_z)
        mine_path_anchor = (entrance[0] + mine_connector_x, entrance[2] + mine_connector_z)

        def build_mining_curve(
            node, target_start, target_end, label, *,
            start_position=None, end_position=None):
            """Build a restrained terrain-following mining Bezier curve."""
            target_curve = next((child for child in node.iter()
                                 if tag(child) == "BezierCurve"), None)
            if target_curve is None or len(target_curve) < 2:
                raise ValueError(f"{label} template has no usable BezierCurve.")
            source_points = [parse_position(text(item, "p")) for item in target_curve]
            source_start, source_end = source_points[0], source_points[-1]
            source_dx = source_end[0] - source_start[0]
            source_dz = source_end[2] - source_start[2]
            source_length = math.hypot(source_dx, source_dz)
            target_dx = target_end[0] - target_start[0]
            target_dz = target_end[1] - target_start[1]
            target_length = math.hypot(target_dx, target_dz)
            if source_length <= 0.000001 or target_length <= 0.000001:
                raise ValueError(f"{label} BezierPath has zero length.")

            is_workarea = "1000253" in label
            if is_workarea:
                point_count = max(2, int(self.MINE_WORKAREA_PATH_POINTS))
            else:
                point_count = max(
                    self.MINE_CAVE_PATH_MIN_POINTS,
                    min(self.MINE_CAVE_PATH_MAX_POINTS,
                        int(math.ceil(target_length / max(0.25, self.MINE_PATH_DISTANCE_STEP))) + 1),
                )

            target_ux, target_uz = target_dx / target_length, target_dz / target_length
            target_nx, target_nz = -target_uz, target_ux
            source_ux, source_uz = source_dx / source_length, source_dz / source_length
            source_nx, source_nz = -source_uz, source_ux

            def source_lateral(progress):
                pos = progress * (len(source_points) - 1)
                left = min(len(source_points) - 1, int(math.floor(pos)))
                right = min(len(source_points) - 1, left + 1)
                blend = pos - left
                px = source_points[left][0] * (1.0 - blend) + source_points[right][0] * blend
                pz = source_points[left][2] * (1.0 - blend) + source_points[right][2] * blend
                line_x = source_start[0] + source_dx * progress
                line_z = source_start[2] + source_dz * progress
                lateral = (px - line_x) * source_nx + (pz - line_z) * source_nz
                limit = max(0.0, float(self.MINE_PATH_MAX_LATERAL_OFFSET))
                return max(-limit, min(limit, lateral))

            points = []
            for index in range(point_count):
                progress = index / max(1, point_count - 1)
                lateral = (0.0 if index in (0, point_count - 1)
                           else source_lateral(progress))
                world_x = target_start[0] + target_dx * progress + target_nx * lateral
                world_z = target_start[1] + target_dz * progress + target_nz * lateral
                surface = self._mine_path_surface_height(world_x, world_z, placement["samples"])
                if surface is None:
                    surface = mountain[1] * (1.0 - progress) + entrance[1] * progress
                extra_lift = 0.0 if index == 0 else self.MINE_PATH_EXTRA_LIFT
                points.append((world_x, surface + self.MINE_PATH_CLEARANCE
                               + self.MINE_PATH_HEIGHT_OFFSET + extra_lift, world_z))

            start_surface = self._mine_path_surface_height(target_start[0], target_start[1], placement["samples"])
            if start_surface is None:
                start_surface = mountain[1]
            points[0] = (
                (target_start[0],
                 start_surface + self.MINE_PATH_CLEARANCE + self.MINE_PATH_HEIGHT_OFFSET,
                 target_start[1])
                if start_position is None else start_position
            )
            points[-1] = (
                (target_end[0], mine_position[1], target_end[1])
                if end_position is None else end_position
            )

            items = []
            handle_cap = max(0.05, float(self.MINE_PATH_MAX_HANDLE_LENGTH))
            for index, point in enumerate(points):
                previous_point = points[max(0, index - 1)]
                next_point = points[min(len(points) - 1, index + 1)]
                secant = tuple(next_point[a] - previous_point[a] for a in range(3))
                secant_length = math.sqrt(sum(v * v for v in secant))
                unit = ((target_ux, 0.0, target_uz) if secant_length <= 0.000001
                        else tuple(v / secant_length for v in secant))
                runs = []
                if index > 0:
                    runs.append(math.dist(point, points[index - 1]))
                if index + 1 < len(points):
                    runs.append(math.dist(point, points[index + 1]))
                handle_length = min(handle_cap, (min(runs) if runs else 0.0) / 3.0)
                outgoing = tuple(v * handle_length for v in unit)
                incoming = tuple(-v for v in outgoing)
                item = ET.Element("None")
                ET.SubElement(item, "p").text = format_position(point)
                ET.SubElement(item, "i").text = format_position(incoming)
                ET.SubElement(item, "o").text = format_position(outgoing)
                items.append(item)

            for child in list(target_curve):
                target_curve.remove(child)
            for item in items:
                target_curve.append(item)
            path = target_curve.getparent()
            minimum, maximum = direct(path, "Minimum"), direct(path, "Maximum")
            if minimum is None or maximum is None:
                raise ValueError(f"{label} template lacks Bezier bounds.")
            minimum.text = format_position(tuple(min(p[a] for p in points) for a in range(3)))
            maximum.text = format_position(tuple(max(p[a] for p in points) for a in range(3)))
            return points, math.atan2(target_dz, target_dx)

        # Generate 100419 independently, but make it share 1000029's exact
        # connector with 1000253. Its start lies outside the Cave anchor on the
        # side away from the MineSlot, as in the native groups.
        cave_to_mine_x = mine_path_anchor[0] - cave_midpoint[0]
        cave_to_mine_z = mine_path_anchor[1] - cave_midpoint[2]
        cave_to_mine_length = math.hypot(cave_to_mine_x, cave_to_mine_z)
        if cave_to_mine_length <= 0.000001:
            raise ValueError("Cave and MineSlot connector are identical.")
        cave_unit_x = cave_to_mine_x / cave_to_mine_length
        cave_unit_z = cave_to_mine_z / cave_to_mine_length
        cave_start = (
            cave_midpoint[0] - cave_unit_x * self.MINE_CAVE_PATH_START_OFFSET,
            cave_midpoint[2] - cave_unit_z * self.MINE_CAVE_PATH_START_OFFSET,
        )
        workarea_path_start, workarea_path_end = self.mine_workarea_path_endpoints(
            mine_position,
            workarea_position,
            mine_path_anchor,
            workarea_path_anchor,
        )
        cave_points, _cave_path_rotation = build_mining_curve(
            cave, cave_start, mine_path_anchor, "Mine Cave 100419",
            end_position=workarea_path_start)
        cave_direction = math.atan2(cave_to_mine_x, cave_to_mine_z)
        cave_direction_node = direct(cave, "Direction")
        if cave_direction_node is None:
            cave_direction_node = ET.Element("Direction")
            cave_position_node = direct(cave, "Position")
            cave.insert(list(cave).index(cave_position_node) + 1,
                        cave_direction_node)
        cave_direction_node.text = game_number(cave_direction)
        cave_mesh = direct(cave, "Mesh")
        cave_orientation = direct(cave_mesh, "Orientation") if cave_mesh is not None else None
        if cave_orientation is not None:
            cave_half_yaw = cave_direction / 2.0
            cave_orientation.text = " ".join(game_number(value) for value in (
                0.0, -math.sin(cave_half_yaw), 0.0,
                math.cos(cave_half_yaw)))
        workarea_points, workarea_path_rotation = build_mining_curve(
            workarea,
            mine_path_anchor, workarea_path_anchor,
            "Mine Work Area 1000253",
            start_position=workarea_path_start,
            end_position=workarea_path_end,
        )

        # Orient 1000253 from the direct Work Area -> MineSlot axis. The Bezier
        # is intentionally ignored so terrain shaping cannot rotate the object.
        workarea_axis_x = entrance[0] - mountain[0]
        workarea_axis_z = entrance[2] - mountain[2]
        if math.hypot(workarea_axis_x, workarea_axis_z) <= 0.000001:
            raise ValueError("Mine Work Area 1000253 placement axis is zero-length.")
        # 1000253 orientation is independent from Bezier curvature. Native mine
        # pairs use the exact opposite raster direction of 1000029.
        workarea_direction = (mine_direction + math.pi) % (2.0 * math.pi)
        workarea_direction_node = direct(workarea, "Direction")
        if workarea_direction_node is None:
            workarea_direction_node = ET.Element("Direction")
            workarea_position_node = direct(workarea, "Position")
            workarea.insert(list(workarea).index(workarea_position_node) + 1, workarea_direction_node)
        workarea_object_direction = (workarea_direction + (math.pi / 2.0)) % (2.0 * math.pi)
        # Mirror 1000253 on the opposite local model axis. In the model's rotated
        # coordinate convention this corrects left/right without the previous
        # horizontal-angle negation that also inverted the visual up/down cases.
        workarea_object_direction = (math.pi - workarea_object_direction) % (2.0 * math.pi)
        workarea_direction_node.text = game_number(workarea_object_direction)
        workarea_mesh = direct(workarea, "Mesh")
        workarea_orientation = direct(workarea_mesh, "Orientation") if workarea_mesh is not None else None
        if workarea_orientation is not None:
            half = workarea_object_direction / 2.0
            workarea_orientation.text = " ".join(game_number(v) for v in (
                0.0, -math.sin(half), 0.0, math.cos(half)))

        # Both generated paths share the object-relative MineSlot endpoint.
        connector_error = math.sqrt(sum(
            (cave_points[-1][axis] - workarea_points[0][axis]) ** 2
            for axis in range(3)))
        if connector_error > 0.001:
            raise ValueError(
                "100419 and 1000253 do not share the MineSlot connector.")
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