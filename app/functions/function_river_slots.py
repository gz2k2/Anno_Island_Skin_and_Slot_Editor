"""Specialized native RiverSlot placement methods extracted from function_island_slots."""

from app.functions.function_island_slots import *  # noqa: F401,F403


class RiverSlotEditingMixin:
    # Native RiverSlot 117741 / Work Area 117742 settings.
    RIVER_MIN_DISTANCE = 6.0
    RIVER_MAX_DISTANCE = 15.0

    # Additive Y correction in world-height units. Applied equally to RiverSlot,
    # Work Area, MapName positions and every transformed Bezier point.
    # Vertical correction for RiverSlot and Work Area.
    RIVER_HEIGHT_OFFSET = 0.2

    # Additional correction applied only to BezierPath points.
    RIVER_PATH_HEIGHT_OFFSET = 0.0

    # Minimum distance between an inner Bezier point and terrain. Endpoints are
    # never raised, so both building connections remain exact.
    RIVER_PATH_TERRAIN_CLEARANCE = 0.10

    # Smoothstep produces almost level transitions at Slot and Work Area.
    RIVER_PATH_SMOOTH_HEIGHT = True

    def _river_heightmap(self):
        """Return cached (width, height, signed values) from Gamedata HeightMap."""
        game_tree = getattr(self, "_island_slot_ram_game_tree", None)
        if game_tree is None:
            return None
        root = game_tree.getroot()
        root_id = id(root)
        cached = getattr(self, "_river_heightmap_cache", None)
        if cached is not None and cached[0] == root_id:
            return cached[1]
        result = None
        for node in root.iter():
            if tag(node) != "HeightMap":
                continue
            width_node = direct(node, "Width")
            height_node = direct(node, "Height")
            values_node = direct(node, "HeightMap")
            if width_node is None or height_node is None or values_node is None:
                continue
            try:
                width = int((width_node.text or "").strip())
                height = int((height_node.text or "").strip())
                raw_values = [int(value) for value in (values_node.text or "").split()]
            except (TypeError, ValueError):
                continue
            if width <= 1 or height <= 1 or len(raw_values) != width * height:
                continue
            values = tuple(
                value if value < 32768 else value - 65536
                for value in raw_values)
            result = (width, height, values)
            break
        self._river_heightmap_cache = (root_id, result)
        return result

    def _river_terrain_height(self, x, z, samples):
        """Sample the Gamedata HeightMap; fall back to nearby object positions."""
        heightmap = self._river_heightmap()
        if heightmap is not None:
            width, height, values = heightmap
            grid_x = float(x) * 2.0
            grid_z = float(z) * 2.0
            if 0.0 <= grid_x <= width - 1 and 0.0 <= grid_z <= height - 1:
                x0 = int(math.floor(grid_x))
                z0 = int(math.floor(grid_z))
                x1 = min(x0 + 1, width - 1)
                z1 = min(z0 + 1, height - 1)
                fx, fz = grid_x - x0, grid_z - z0
                h00 = values[z0 * width + x0] / 128.0
                h10 = values[z0 * width + x1] / 128.0
                h01 = values[z1 * width + x0] / 128.0
                h11 = values[z1 * width + x1] / 128.0
                top = h00 + (h10 - h00) * fx
                bottom = h01 + (h11 - h01) * fx
                return top + (bottom - top) * fz
        return estimate_nearby_height(x, z, samples)

    @staticmethod
    def _river_half_coordinate(value):
        """Snap a world coordinate to the required n + 0.5 grid."""
        return math.floor(float(value)) + 0.5

    @staticmethod
    def _river_geometry(entrance, work_position):
        """Calculate native RiverSlot length, direction and real vector.

        Length is the dominant-axis distance. Direction is derived from the
        final positions after the mandatory one-tile Work Area offset. The
        real vector/length remains available for Bezier transformation.
        """
        dx = work_position[0] - entrance[0]
        dz = work_position[2] - entrance[2]
        length = max(abs(dx), abs(dz))
        if abs(dx) >= abs(dz):
            direction = math.pi / 2.0 if dx >= 0.0 else 3.0 * math.pi / 2.0
        else:
            direction = 0.0 if dz < 0.0 else math.pi
        return {
            "dx": dx, "dz": dz,
            "length": length,
            "real_length": math.hypot(dx, dz),
            "real_angle": math.atan2(dz, dx),
            "direction": direction,
        }

    @classmethod
    def _island_slot_snap_river_target(cls, entrance, target_x, target_z):
        """Create the TXT-defined Work Area position.

        Both points stay on n + 0.5 coordinates. The dominant cursor axis
        defines the main length, while the Work Area is exactly one tile off
        that main axis. The one-tile offset rotates with the chosen direction.
        """
        entrance_x = cls._river_half_coordinate(entrance[0])
        entrance_z = cls._river_half_coordinate(entrance[2])
        target_x = cls._river_half_coordinate(target_x)
        target_z = cls._river_half_coordinate(target_z)
        delta_x = target_x - entrance_x
        delta_z = target_z - entrance_z
        if abs(delta_x) >= abs(delta_z):
            side = 1.0 if delta_x >= 0.0 else -1.0
            return target_x, entrance_z + side
        side = -1.0 if delta_z >= 0.0 else 1.0
        return entrance_x + side, target_z

    def _slot_map_selected_river_guids(self):
        """Return the GUID pair selected in the Slot Map River Slot Type menu."""
        variable = getattr(self, "slot_map_river_type_var", None)
        selected = str(variable.get() if variable is not None else "").strip()
        guids = getattr(self, "slot_map_river_type_guids", {}).get(selected)
        if guids is None:
            messagebox.showerror(
                "River Slot Type", "Select a valid River Slot Type.",
                parent=getattr(self, "slot_map_window", None),
            )
            return None
        return tuple(str(guid) for guid in guids)

    def _island_slot_add_riverslot_at_event(self, event):
        """Enter free two-click RiverSlot placement; the menu click is not a placement click."""
        guids = self._slot_map_selected_river_guids()
        if guids is None:
            return
        primary_guid, workarea_guid = guids
        self._island_slot_cancel_mine_placement(silent=True)
        samples, source = self._island_slot_height_samples()
        self._mine_placement = {
            "kind": "river", "name": "Riverslot",
            "entrance": None, "samples": samples, "source": source,
            "primary_guid": primary_guid, "workarea_guid": workarea_guid,
        }
        self.slot_map_allow_dot_movement_var.set(False)
        self._slot_map_dot_movement_changed()
        self.slot_map_canvas.focus_set()
        self.status_var.set(
            f"Move the mouse and left-click to place RiverSlot {primary_guid}; "
            "right-click or Esc to cancel.")
        self._island_slot_draw_mine_preview(event)

    def _island_slot_commit_native_river_pair(
            self, placement, entrance, work_position, samples, source, status):
        go, mo, gp, mp = self._island_slot_sources()
        if self._island_slot_ram_game_tree is None or self._island_slot_ram_map_tree is None:
            self._island_slot_ram_game_tree = self._slot_parse_xml(
                gp if gp.is_file() else go)[0]
            self._island_slot_ram_map_tree = self._slot_parse_xml(
                mp if mp.is_file() else mo)[0]
        game_tree = self._island_slot_ram_game_tree
        map_tree = self._island_slot_ram_map_tree
        game_root, map_root = game_tree.getroot(), map_tree.getroot()
        container = game_object_container(game_root)
        primary_guid = str(placement.get("primary_guid", "")).strip()
        workarea_guid = str(placement.get("workarea_guid", "")).strip()
        current_guids = self._slot_map_selected_river_guids()
        if current_guids is None or current_guids != (primary_guid, workarea_guid):
            raise ValueError(
            "The selected River Slot Type changed during placement. "
                "Cancel and place the RiverSlot again.")
        river, workarea = river_pair()
        set_text(river, "guid", primary_guid)
        set_text(workarea, "guid", workarea_guid)
        used = all_ids(map_root, game_root)
        river_id, work_id = allocate_id_family_from_used(used, 2)
        folder = new_folder_id_from_tree(game_root)

        # Raise the complete River family as one vertical unit. Keeping one
        # shared offset prevents anchors, MapName and Bezier geometry drifting.
        entrance = (
            entrance[0], entrance[1] + self.RIVER_HEIGHT_OFFSET, entrance[2])
        work_position = (
            work_position[0],
            work_position[1] + self.RIVER_HEIGHT_OFFSET,
            work_position[2],
        )

        geometry = self._river_geometry(entrance, work_position)
        direction = geometry["direction"]

        for node, oid, guid, position in (
                (river, river_id, primary_guid, entrance),
                (workarea, work_id, workarea_guid, work_position)):
            set_text(node, "ID", oid)
            set_text(node, "ObjectFolderID", folder)
            set_text(node, "Position", format_position(position))
            set_text(node, "guid", guid)
            direction_node = direct(node, "Direction")
            if direction_node is None:
                direction_node = ET.Element("Direction")
                position_node = direct(node, "Position")
                node.insert(list(node).index(position_node) + 1, direction_node)
            direction_node.text = game_number(direction)
            orientation = direct(direct(node, "Mesh"), "Orientation")
            half = direction / 2.0
            orientation.text = " ".join(game_number(v) for v in (
                0.0, -math.sin(half), 0.0, math.cos(half)))

        # Custom River Work Areas use a local two-point BezierPath. The path
        # origin is the Work Area connection (0/0/0); its second point runs
        # back toward the RiverSlot. This matches the working 1999002330/2331
        # pair and avoids writing absolute world coordinates into BezierCurve.
        bezier = direct(workarea, "BezierPath")
        path = direct(bezier, "Path") if bezier is not None else None
        curve = direct(path, "BezierCurve") if path is not None else None
        if curve is None or len(curve) != 2:
            raise ValueError(
                "Native River Work Area template must have a two-point BezierPath.")

        main_length = geometry["length"]
        path_length = max(0.0, main_length - 6.0 + 0.32393)
        height_delta = entrance[1] - work_position[1]

        # Direction uses the object's cardinal orientation. The local path end
        # points in the opposite direction, from Work Area back to RiverSlot.
        endpoint = (
            -math.sin(direction) * path_length,
            height_delta,
            math.cos(direction) * path_length,
        )
        endpoint = tuple(0.0 if abs(value) < 0.0000001 else value
                         for value in endpoint)
        origin = (0.0, 0.0, 0.0)

        # These tangents are taken from the verified custom 1999002331 Work
        # Area. They describe the local connector profile and must not be
        # rotated into world coordinates or scaled with the object distance.
        incoming = (-0.39575043, -0.014931966, 0.0014282227)
        outgoing = (0.39575043, 0.014931966, -0.0014282227)
        points = list(curve)
        for item, point in zip(points, (origin, endpoint)):
            direct(item, "p").text = format_position(point)
            direct(item, "i").text = format_position(incoming)
            direct(item, "o").text = format_position(outgoing)

        direct(path, "TangentScale").text = game_number(0.3)
        # The custom format stores the two anchors directly rather than
        # component-wise mathematical bounds.
        direct(path, "Minimum").text = format_position(origin)
        direct(path, "Maximum").text = format_position(endpoint)

        transaction = XMLAppendTransaction()
        try:
            transaction.append(container, river)
            transaction.append(container, workarea)
            append_map_entry(
                map_root, "4", river_id, primary_guid,
                format_position(entrance), transaction=transaction)
            append_map_entry(
                map_root, "3", work_id, workarea_guid,
                format_position(work_position), transaction=transaction)
            containers = mine_object_group_containers(game_root)
            used_group_names = {
                (child.text or "").strip()
                for groups in containers for child in groups
                if direct(child, "GameObjects") is None and (child.text or "").strip()
            }
            group_name = "New Group"
            number = 1
            while group_name in used_group_names:
                group_name = f"New Group {number}"
                number += 1
            for groups in containers:
                name_node = ET.Element("None")
                name_node.text = group_name
                transaction.append(groups, name_node)
                group = ET.Element("None")
                members = ET.SubElement(group, "GameObjects")
                for oid in (river_id, work_id):
                    ET.SubElement(members, "None").text = oid
                transaction.append(groups, group)
            validate_pair(map_root, game_root)
        except Exception:
            transaction.rollback()
            raise
        self._island_slot_ram_game_tree = game_tree
        self._island_slot_ram_map_tree = map_tree
        StatusWindowTemplate.update(status, fraction=1)
        self.status_var.set(
            f"Added RiverSlot {primary_guid}/{workarea_guid} | ID family: "
            f"{river_id}, {work_id} | Group: {group_name} | Height: {source}")
        self._refresh_open_slot_map()
