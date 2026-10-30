"""Specialized MineSlot placement methods extracted from function_island_slots."""

from app.functions.function_island_slots import *  # noqa: F401,F403


class MiningSlotEditingMixin:
    # MineSlot settings
    MINE_SLOT_VARIANTS = (
        ("MineSlot (OW, NW Gold)", "1000029"),
        ("MineSlot (NW)", "614"),
        ("MineSlot (Arctic)", "116037"),
    )
    MINE_MIN_DISTANCE = 2.0
    MINE_MAX_DISTANCE = 20.0

    # Cave GUID 100419 settings.
    # 0.0 = MineSlot, 0.25 = 25 percent, 0.5 = midpoint, 1.0 = Work Area.
    MINE_CAVE_DISTANCE_FRACTION = 0.25
    # 1.0 = unchanged, 1.5 = 50 percent higher, 0.8 = 20 percent lower.
    MINE_CAVE_HEIGHT_MULTIPLIER = 1.0
    def _island_slot_add_mineslot_at_event(self, event, display_name, guid):
        """Start two-click mine placement; do not change XML yet."""
        self._island_slot_cancel_mine_placement(silent=True)
        x, z = self._island_slot_world(event)
        x, z = math.floor(x) + 0.5, math.floor(z) + 0.5
        samples, source = self._island_slot_height_samples()
        y = estimate_nearby_height(x, z, samples)
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
        for node, oid, guid, position in ((mine,mine_id,target_guid,entrance),(workarea,work_id,MINE_WORKAREA_GUID,mountain)):
            set_text(node,"ID",oid); set_text(node,"Position",format_position(position))
            guid_node=direct(node,"guid"); guid_node.text=guid
            folder_node=direct(node,"ObjectFolderID")
            if folder_node is None:
                folder_node=ET.Element("ObjectFolderID"); node.insert(2,folder_node)
            folder_node.text=folder
        # Place Cave 100419 exactly halfway between MineSlot and Work Area.
        # Preserve the complete native five-point Cave path and rotate/translate
        # that geometry around the Cave template's own anchor to the midpoint.
        original_cave_position = parse_position(text(cave, "Position"))
        original_master_direction = math.pi
        cave_fraction = self.MINE_CAVE_DISTANCE_FRACTION
        midpoint_x = entrance[0] + (mountain[0] - entrance[0]) * cave_fraction
        midpoint_z = entrance[2] + (mountain[2] - entrance[2]) * cave_fraction
        midpoint_y = estimate_nearby_height(
            midpoint_x, midpoint_z, placement["samples"])
        if midpoint_y is None or midpoint_y <= 0:
            midpoint_y = entrance[1] + (mountain[1] - entrance[1]) * cave_fraction
        midpoint_y *= self.MINE_CAVE_HEIGHT_MULTIPLIER
        cave_midpoint = (midpoint_x, midpoint_y, midpoint_z)
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
            lambda x, z: estimate_nearby_height(x, z, placement["samples"]),
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
        curve=next((n for n in workarea.iter() if tag(n)=="BezierCurve"),None)
        if curve is None: raise ValueError("Work Area template has no BezierCurve.")
        for child in list(curve): curve.remove(child)
        points=[]
        for index in range(9):
            f=index/8; x=mountain[0]+(entrance[0]-mountain[0])*f; z=mountain[2]+(entrance[2]-mountain[2])*f
            y=estimate_nearby_height(x,z,placement["samples"])
            if y is None or y <= 0: raise ValueError("Mine path crosses invalid or underwater terrain.")
            points.append((x,y,z))
        for index,point in enumerate(points):
            a=points[max(0,index-1)]; b=points[min(8,index+1)]; tangent=tuple((b[i]-a[i])/6 for i in range(3))
            item=ET.SubElement(curve,"None"); ET.SubElement(item,"p").text=format_position(point)
            ET.SubElement(item,"i").text=format_position(tuple(-v for v in tangent)); ET.SubElement(item,"o").text=format_position(tangent)
        path=curve.getparent(); minimum=direct(path,"Minimum"); maximum=direct(path,"Maximum")
        minimum.text=format_position(tuple(min(p[i] for p in points) for i in range(3)))
        maximum.text=format_position(tuple(max(p[i] for p in points) for i in range(3)))
        StatusWindowTemplate.update(status,fraction=.7)
        append_pretty(container,mine); append_pretty(container,workarea); append_pretty(container,cave)
        append_map_entry(map_root,MINE_PRIMARY_GROUP,mine_id,target_guid,format_position(entrance))
        append_map_entry(map_root,MINE_WORKAREA_GROUP,work_id,MINE_WORKAREA_GUID,format_position(mountain))
        append_map_entry(map_root,MINE_CAVE_GROUP,cave_id,MINE_CAVE_GUID,text(cave, "Position"))
        group_name = append_mine_object_group(game_root, work_id, mine_id, cave_id)
        validate_pair(map_root,game_root)
        self._island_slot_ram_game_tree,self._island_slot_ram_map_tree=game_tree,map_tree
        StatusWindowTemplate.update(status,fraction=1)
        self.status_var.set(f"Added {placement['name']} from master {MINE_MASTER_GUID} as GUID {target_guid} with Work Area | IDs: {mine_id}, {work_id} | Folder: {folder}")
        self._refresh_open_slot_map()
