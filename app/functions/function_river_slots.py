"""Specialized native RiverSlot placement methods extracted from function_island_slots."""

from app.functions.function_island_slots import *  # noqa: F401,F403


class RiverSlotEditingMixin:
    # Native RiverSlot 117741 / Work Area 117742 settings.
    RIVER_MIN_DISTANCE = 6.0
    RIVER_MAX_DISTANCE = 15.0

    # Additive Y correction in world-height units. Applied equally to RiverSlot,
    # Work Area, MapName positions and every transformed Bezier point.
    RIVER_HEIGHT_OFFSET = 0.5

    @staticmethod
    def _island_slot_snap_river_target(entrance, target_x, target_z):
        """Snap the second RiverSlot point to the nearest 90-degree world axis.

        The dominant cursor delta chooses horizontal or vertical placement. The
        target remains on the existing half-cell grid because the unchanged
        coordinate comes from the already snapped entrance.
        """
        entrance_x, _entrance_y, entrance_z = entrance
        delta_x = target_x - entrance_x
        delta_z = target_z - entrance_z
        if abs(delta_x) >= abs(delta_z):
            return target_x, entrance_z
        return entrance_x, target_z

    def _island_slot_add_riverslot_at_event(self, event):
        """Start native 117741/117742 two-click placement."""
        self._island_slot_cancel_mine_placement(silent=True)
        x, z = self._island_slot_world(event)
        x, z = math.floor(x) + 0.5, math.floor(z) + 0.5
        samples, source = self._island_slot_height_samples()
        y = estimate_nearby_height(x, z, samples)
        if y is None or y <= 0:
            messagebox.showerror(
                "Add RiverSlot", "RiverSlot must be placed on emerged terrain.",
                parent=self.slot_map_window)
            return
        self._mine_placement = {
            "kind": "river", "name": "Riverslot",
            "entrance": (x, y, z), "samples": samples, "source": source,
        }
        self.slot_map_allow_dot_movement_var.set(False)
        self._slot_map_dot_movement_changed()
        self.slot_map_canvas.focus_set()
        self.status_var.set(
            f"RiverSlot 117741 selected at X/Z {x:g} / {z:g}. "
            "Left-click to place Work Area 117742; right-click or Esc to cancel.")
        self._island_slot_draw_mine_preview(None)

    def _island_slot_commit_native_river_pair(
            self, entrance, work_position, samples, source, status):
        go, mo, gp, mp = self._island_slot_sources()
        if self._island_slot_ram_game_tree is None or self._island_slot_ram_map_tree is None:
            self._island_slot_ram_game_tree = self._slot_parse_xml(
                gp if gp.is_file() else go)[0]
            self._island_slot_ram_map_tree = self._slot_parse_xml(
                mp if mp.is_file() else mo)[0]
        game_tree = deepcopy(self._island_slot_ram_game_tree)
        map_tree = deepcopy(self._island_slot_ram_map_tree)
        game_root, map_root = game_tree.getroot(), map_tree.getroot()
        container = game_object_container(game_root)
        river, workarea = river_pair()
        set_text(workarea, "guid", "117742")
        used = all_ids(map_root, game_root)
        river_id, work_id = allocate_verified_id_family(
            map_root, game_root, used, 2)
        folder = new_folder_id(object_records(game_root))

        # Raise the complete River family as one vertical unit. Keeping one
        # shared offset prevents anchors, MapName and Bezier geometry drifting.
        entrance = (
            entrance[0], entrance[1] + self.RIVER_HEIGHT_OFFSET, entrance[2])
        work_position = (
            work_position[0],
            work_position[1] + self.RIVER_HEIGHT_OFFSET,
            work_position[2],
        )

        dx = work_position[0] - entrance[0]
        dz = work_position[2] - entrance[2]
        if abs(dx) >= abs(dz):
            direction = math.pi / 2.0 if dx >= 0 else 3.0 * math.pi / 2.0
        else:
            direction = 0.0 if dz < 0 else math.pi

        for node, oid, guid, position in (
                (river, river_id, "117741", entrance),
                (workarea, work_id, "117742", work_position)):
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

        # Preserve the complete native 117742 BezierPath. Map its original
        # RiverSlot -> Work Area frame onto the two user-selected points using a
        # rotation plus uniform length scale; then resolve path Y from terrain.
        bezier = direct(workarea, "BezierPath")
        curve = direct(direct(bezier, "Path"), "BezierCurve") if bezier is not None else None
        if curve is None or len(curve) != 2:
            raise ValueError("Native River Work Area template must have a two-point BezierPath.")
        template_river, template_work = river_pair()
        source_slot = parse_position(text(template_river, "Position"))
        source_work = parse_position(text(template_work, "Position"))
        source_dx = source_work[0] - source_slot[0]
        source_dz = source_work[2] - source_slot[2]
        target_dx = work_position[0] - entrance[0]
        target_dz = work_position[2] - entrance[2]
        source_length = math.hypot(source_dx, source_dz)
        target_length = math.hypot(target_dx, target_dz)
        if source_length <= 0 or target_length <= 0:
            raise ValueError("RiverSlot and Work Area must not occupy the same position.")
        source_angle = math.atan2(source_dz, source_dx)
        target_angle = math.atan2(target_dz, target_dx)
        rotation = target_angle - source_angle
        cosine, sine = math.cos(rotation), math.sin(rotation)
        scale = target_length / source_length

        def transform_xz(vector_x, vector_z, apply_scale=True):
            factor = scale if apply_scale else 1.0
            x = vector_x * factor
            z = vector_z * factor
            return (x * cosine - z * sine, x * sine + z * cosine)

        transformed_points = []
        for item in curve:
            point = parse_position(text(item, "p"))
            relative_x = point[0] - source_slot[0]
            relative_z = point[2] - source_slot[2]
            offset_x, offset_z = transform_xz(relative_x, relative_z)
            point_x = entrance[0] + offset_x
            point_z = entrance[2] + offset_z
            point_y = estimate_nearby_height(point_x, point_z, samples)
            if point_y is None or point_y <= 0:
                unshifted_entrance_y = entrance[1] - self.RIVER_HEIGHT_OFFSET
                point_y = unshifted_entrance_y + (
                    work_position[1] - entrance[1]) * min(
                        1.0, max(0.0, math.hypot(offset_x, offset_z) / target_length))
            point_y += self.RIVER_HEIGHT_OFFSET
            transformed_point = (point_x, point_y, point_z)
            direct(item, "p").text = format_position(transformed_point)
            transformed_points.append(transformed_point)
            for tangent_name in ("i", "o"):
                tangent = parse_position(text(item, tangent_name))
                tangent_x, tangent_z = transform_xz(tangent[0], tangent[2])
                direct(item, tangent_name).text = format_position(
                    (tangent_x, tangent[1] * scale, tangent_z))
        path = direct(bezier, "Path")
        direct(path, "Minimum").text = format_position(tuple(
            min(point[axis] for point in transformed_points) for axis in range(3)))
        direct(path, "Maximum").text = format_position(tuple(
            max(point[axis] for point in transformed_points) for axis in range(3)))

        append_pretty(container, river)
        append_pretty(container, workarea)
        append_map_entry(map_root, "4", river_id, "117741", format_position(entrance))
        append_map_entry(map_root, "3", work_id, "117742", format_position(work_position))
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
            append_pretty(groups, name_node)
            group = ET.Element("None")
            members = ET.SubElement(group, "GameObjects")
            for oid in (river_id, work_id):
                ET.SubElement(members, "None").text = oid
            append_pretty(groups, group)
        validate_pair(map_root, game_root)
        self._island_slot_ram_game_tree = game_tree
        self._island_slot_ram_map_tree = map_tree
        StatusWindowTemplate.update(status, fraction=1)
        self.status_var.set(
            f"Added native RiverSlot 117741/117742 | ID family: "
            f"{river_id}, {work_id} | Group: {group_name} | Height: {source}")
        self._refresh_open_slot_map()
