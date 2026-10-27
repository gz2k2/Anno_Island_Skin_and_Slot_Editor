"""Object Map rectangular selection and region-only object edits."""
import math
import random
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from app.templates.template_map_view import MapViewTemplate
from app.templates.template_popup import PopupTemplate
from app.templates.template_statuswindow import StatusWindowTemplate
from app.templates.template_table import TemplateTable, TableColumn
from app.functions.function_place_object import ObjectMapSession, preview_placement
from app.functions.function_density import child, position, local_tag, usage_counts


def region_entries(session, area, categories, visible_categories=None):
    lo,hi,bottom,top=area
    grid=next(n for n in session.tree.getroot().iter() if local_tag(n)=='PropGrid')
    instances=child(grid,'Instances')
    grouped={}
    if instances is None:return grouped
    for ordinal,node in enumerate(instances):
        p=position(node)
        try:index=int(child(node,'Index').text)
        except (AttributeError,ValueError,TypeError):continue
        category=categories.get(index,'Unknown')
        if (p is not None and lo<=p[0]<=hi and bottom<=p[2]<=top
                and (visible_categories is None or category in visible_categories)):
            grouped.setdefault(category,[]).append((ordinal,index))
    return grouped


def change_region_count(session, area, categories, category, increase, bounds, progress, percent=10.0, rng=None, visible_categories=None):
    rng=rng or random.Random()
    percent=float(str(percent).replace(',', '.'))
    if not math.isfinite(percent) or not 0 < percent <= 100:
        raise ValueError('Density (%) must be greater than 0 and at most 100.')
    grouped=region_entries(session,area,categories,visible_categories)
    entries=grouped.get(category,[])
    if not entries:raise ValueError('No objects of this Type remain inside the selected area.')
    # Match Change Density: percentage is based only on this category's current
    # instance count inside the selected rectangle, rounded to the nearest object.
    amount=max(1, math.floor(len(entries)*percent/100+.5))
    if increase:
        indices=sorted({index for _,index in entries})
        paths=session.paths()
        selected=[paths[index] for index in indices]
        lo,hi,bottom,top=area
        result=preview_placement(
            session, selected, amount, ((lo+hi)/2,(bottom+top)/2),
            bounds, progress, rng=rng, area=area)
    else:
        if amount > len(entries):
            raise ValueError(
                f'Only {len(entries)} objects of this Type are available inside the selected area. '
                f'Choose a lower Density (%) value. The current selection contains {len(entries)} objects.')
        result=session.fork()
        # Sample ordinals once and remove descending so indices stay valid.
        selected_ordinals=sorted(
            (ordinal for ordinal,_index in rng.sample(entries, amount)), reverse=True)
        for completed,ordinal in enumerate(selected_ordinals,1):
            result.delete_instance(ordinal)
            progress(completed,amount)
    return result


class MapSelectionMixin:
    def _map_world_clamped(self,event):
        canvas=self.object_configuration_map_canvas
        lo,hi,bottom,top=self.object_configuration_map_bounds
        scale=min((canvas.winfo_width()-2*MapViewTemplate.MAP_MARGIN)/(hi-lo),
                  (canvas.winfo_height()-2*MapViewTemplate.MAP_MARGIN)/(top-bottom))*self.object_configuration_map_shared_zoom
        if scale<=0:raise ValueError('Map viewport is too small.')
        left=(canvas.winfo_width()-(hi-lo)*scale)/2+self.object_configuration_map_shared_pan_x
        upper=(canvas.winfo_height()-(top-bottom)*scale)/2+self.object_configuration_map_shared_pan_y
        return (min(hi,max(lo,lo+(event.x-left)/scale)),
                min(top,max(bottom,top-(event.y-upper)/scale)))

    def _map_selection_clear(self, _event=None):
        self._map_selection_area = None
        self._map_lasso_points = []
        self._map_selection_anchor = None
        self._map_selection_screen_start = None
        self._map_selection_dragging = False
        canvas = getattr(self, "object_configuration_map_canvas", None)
        if canvas is not None and canvas.winfo_exists():
            canvas.delete("object_selection")
        return "break" if _event is not None else None

    def _map_lasso_point(self, event):
        if self._tmc_ram_is_busy():
            return "break"
        try:
            world = self._map_world_clamped(event)
        except ValueError:
            return "break"
        points = getattr(self, "_map_lasso_points", None)
        if points is None:
            points = self._map_lasso_points = []
        if not points:
            self._map_selection_area = None
        points.append(world)
        if len(points) >= 3:
            xs = [point[0] for point in points]
            zs = [point[1] for point in points]
            self._map_selection_area = (min(xs), max(xs), min(zs), max(zs))
        self._map_selection_draw()
        selected = sum(
            1 for point in self.object_configuration_map_points
            if len(points) >= 3 and MapViewTemplate.point_in_polygon(point[1], point[2], points)
        )
        self.object_configuration_map_selection_var.set(
            f"Lasso points: {len(points)} | Selected objects: {selected}"
        )
        return "break"

    def _map_selection_start(self,event):
        if self._tmc_ram_is_busy():return 'break'
        self._map_lasso_points = []
        try:self._map_selection_anchor=self._map_world_clamped(event)
        except ValueError:return 'break'
        self._map_selection_screen_start=(event.x,event.y)
        self._map_selection_dragging=True
        self._map_selection_previous=getattr(self,'_map_selection_area',None)
        self._map_selection_area=None
        self._map_selection_draw()
        return 'break'

    def _map_selection_move(self,event):
        if not getattr(self,'_map_selection_dragging',False):return 'break'
        try:x,z=self._map_world_clamped(event)
        except ValueError:return 'break'
        ax,az=self._map_selection_anchor
        self._map_selection_area=(min(ax,x),max(ax,x),min(az,z),max(az,z))
        self._map_selection_draw()
        return 'break'

    def _map_selection_end(self,event):
        if not getattr(self,'_map_selection_dragging',False):return 'break'
        self._map_selection_move(event)
        self._map_selection_dragging=False
        sx,sy=self._map_selection_screen_start
        area=getattr(self,'_map_selection_area',None)
        if math.hypot(event.x-sx,event.y-sy)<5 or area is None or area[0]>=area[1] or area[2]>=area[3]:
            self._map_selection_area=None
            self._on_object_configuration_map_click(event)
        self._map_selection_draw()
        return 'break'

    def _map_selection_draw(self):
        canvas=self.object_configuration_map_canvas
        if canvas is None or not canvas.winfo_exists():return
        canvas.delete('object_selection')
        area=getattr(self,'_map_selection_area',None)
        polygon=getattr(self,'_map_lasso_points',())
        if area is None and not polygon:return
        lo,hi,bottom,top=self.object_configuration_map_bounds
        scale=min((canvas.winfo_width()-2*MapViewTemplate.MAP_MARGIN)/(hi-lo),
                  (canvas.winfo_height()-2*MapViewTemplate.MAP_MARGIN)/(top-bottom))*self.object_configuration_map_shared_zoom
        left=(canvas.winfo_width()-(hi-lo)*scale)/2+self.object_configuration_map_shared_pan_x
        upper=(canvas.winfo_height()-(top-bottom)*scale)/2+self.object_configuration_map_shared_pan_y
        if polygon:
            screen=[]
            for x,z in polygon:
                screen.extend((left+(x-lo)*scale, upper+(top-z)*scale))
            for index in range(0, len(screen), 2):
                canvas.create_oval(screen[index]-4, screen[index+1]-4,
                                   screen[index]+4, screen[index+1]+4,
                                   fill="#00D4FF", outline="#ffffff",
                                   tags="object_selection")
            if len(screen) >= 4:
                canvas.create_line(*screen, fill="#00D4FF", width=2,
                                   dash=(5,3), tags="object_selection")
            if len(screen) >= 6:
                canvas.create_line(screen[-2],screen[-1],screen[0],screen[1],
                                   fill="#00D4FF",width=2,dash=(5,3),tags="object_selection")
            return
        x1,x2,z1,z2=area
        canvas.create_rectangle(left+(x1-lo)*scale,upper+(top-z2)*scale,
            left+(x2-lo)*scale,upper+(top-z1)*scale,
            outline=('#FF3B30' if bool(self.object_configuration_map_allow_dot_movement_var.get()) else '#00D4FF'),width=2,dash=(5,3),tags='object_selection')

    def _map_selection_menu(self,event):
        area=getattr(self,'_map_selection_area',None)
        if area is None:return False
        try:x,z=self._map_world_clamped(event)
        except ValueError:return False
        # Do not clamp outside clicks into a selected edge.
        from app.functions.function_place_object import world_from_click
        try:
            canvas=self.object_configuration_map_canvas
            x,z=world_from_click(event.x,event.y,canvas.winfo_width(),canvas.winfo_height(),
                self.object_configuration_map_bounds,self.object_configuration_map_shared_zoom,
                self.object_configuration_map_shared_pan_x,self.object_configuration_map_shared_pan_y,MapViewTemplate.MAP_MARGIN)
        except ValueError:return False
        polygon=getattr(self,'_map_lasso_points',())
        if len(polygon)>=3:
            if not MapViewTemplate.point_in_polygon(x,z,polygon):return False
        elif not area[0]<=x<=area[1] or not area[2]<=z<=area[3]:return False
        if not self._object_profiles_available(1):return True
        menu=tk.Menu(self.object_configuration_map_canvas,tearoff=0)
        menu.add_command(label='Add',command=lambda:self._place_object_open(event,area=area))
        menu.add_command(label='Change',command=lambda:self._map_region_open(area))
        menu.add_command(label='Remove',command=lambda:self._map_region_remove(area))
        try:menu.tk_popup(event.x_root,event.y_root)
        finally:menu.grab_release()
        return True

    def _map_region_remove(self, area):
        if not self._object_profiles_available(1):
            return
        try:
            cache, session = self._map_session_current()
            current = session if session is not None else ObjectMapSession(cache)
            categories = self._map_region_categories(current, cache)
            grouped = region_entries(current, area, categories, visible_categories=None)
            ordinals = sorted({ordinal for entries in grouped.values() for ordinal, _index in entries})
            polygon = getattr(self, '_map_lasso_points', ())
            if len(polygon) >= 3:
                # map_points() returns six fields:
                # (path_index, x, z, y, position_text, category).
                # region_entries/delete_instances identify instances by ordinal,
                # so preserve the list ordinal separately instead of unpacking it.
                positions = {
                    ordinal: (point[1], point[2])
                    for ordinal, point in enumerate(self._map_preview_points(current))
                }
                ordinals = [
                    ordinal for ordinal in ordinals
                    if ordinal in positions and MapViewTemplate.point_in_polygon(
                        positions[ordinal][0], positions[ordinal][1], polygon
                    )
                ]
            if not ordinals:
                messagebox.showinfo(
                    'Remove Objects', 'No objects were found inside the selected area.',
                    parent=self.object_configuration_map_window,
                )
                return
            if not messagebox.askyesno(
                'Remove Objects',
                f'Remove {len(ordinals)} selected object(s)?\n\n'
                'The XML file will not be changed until Object Map Save is clicked.',
                parent=self.object_configuration_map_window,
                default='no', icon='warning',
            ):
                return
        except ValueError as exc:
            messagebox.showerror('Remove Objects', str(exc), parent=self.object_configuration_map_window)
            return

        def work(progress):
            result = current.fork()
            progress(0, max(1, len(ordinals)))
            removed = result.delete_instances(ordinals)
            progress(removed, max(1, len(ordinals)))
            return result, 'delete-region', self._map_preview_points(result), removed

        self._tmc_ram_begin('RD3D Map Edit', work)

    def _map_region_open(self,area):
        if not self._object_profiles_available(1):return
        try:cache,session=self._map_session_current()
        except ValueError as exc:
            messagebox.showerror('Selected Area',str(exc));return
        old=getattr(self,'_region_window',None)
        if old is not None and old.winfo_exists():old.destroy()
        built=PopupTemplate.create_window(self.object_configuration_map_window,
            title='Change Objects in Selected Area',heading='Objects in Selected Area')
        self._region_window=window=built['window'];self._region_area=tuple(area)
        # Keep this secondary popup owned by and above the Object Map window.
        # PopupTemplate's temporary topmost flag alone is not enough once it is released.
        owner_window = self.object_configuration_map_window
        try:
            if owner_window is not None and owner_window.winfo_exists():
                window.transient(owner_window)
                PopupTemplate.apply_native_titlebar_controls(window)
                window.lift(owner_window)
                PopupTemplate.request_focus(window, delay_ms=100)
        except (tk.TclError, AttributeError):
            pass
        window.grid_columnconfigure(0,weight=1);window.grid_rowconfigure(3,weight=1)
        amount_bar=ctk.CTkFrame(window,fg_color='transparent')
        amount_bar.grid(row=1,column=0,padx=18,pady=(0,8),sticky='ew')
        ctk.CTkLabel(amount_bar,text='Density (%)').pack(side='left',padx=(0,10))
        self._region_amount=tk.StringVar(master=self,value='10')
        ctk.CTkEntry(amount_bar,textvariable=self._region_amount,width=100).pack(side='left')
        ctk.CTkLabel(amount_bar,
            text='Each - / + changes the selected category by this percentage inside the selected area.',
            text_color=PopupTemplate.SECONDARY_TEXT_COLOR).pack(side='left',padx=(12,0))
        self._region_info=tk.StringVar(master=self,value='Loading objects in the selected area...')
        ctk.CTkLabel(window,textvariable=self._region_info,anchor='w',wraplength=950).grid(row=2,column=0,padx=18,pady=(0,8),sticky='ew')
        self._region_table=TemplateTable(window,(
            TableColumn('type','Category',weight=1,anchor='w'),TableColumn('indices','Indices',width=240,anchor='w'),
            TableColumn('count','Count',width=100,anchor='w'),TableColumn('action','Change Density',width=140,anchor='w')),
            row_builder=self._map_region_row)
        self._region_table.grid(row=3,column=0,padx=18,pady=(0,18),sticky='nsew')
        categories=self._map_region_categories(session,cache)
        def work(progress):
            current=session if session is not None else ObjectMapSession(cache)
            visible_categories={name for name,visible in self.object_configuration_map_category_visible.items() if visible}
            grouped=region_entries(current,area,categories,visible_categories)
            progress(1,1)
            return current,'region',self._map_preview_points(current),area,grouped
        self._tmc_ram_begin('RD3D Map Edit',work)

    def _map_region_categories(self,session,cache):
        paths=session.paths() if session is not None else cache.values
        return {i:self._classify_object_configuration_path(path) for i,path in enumerate(paths)}

    def _map_region_row(self,row,data,_index):
        for col,column in enumerate(self._region_table.columns):
            row.grid_columnconfigure(col,weight=column.weight,minsize=column.width+2*TemplateTable.CELL_PADX)
        index_lines = max(1, str(data['indices']).count('\n') + 1)
        row.configure(height=max(self._region_table.row_height, index_lines * 20 + 10))
        for col,key in enumerate(('type','indices','count')):
            width = self._region_table.columns[col].width
            ctk.CTkLabel(row,text=str(data[key]),width=width,anchor='w',justify='left',
                wraplength=width if key == 'indices' else 0,
                font=ctk.CTkFont(size=TemplateTable.BODY_FONT_SIZE),
                text_color=self._object_configuration_picker_color(data['type']) if key=='type' else TemplateTable.BODY_TEXT_COLOR).grid(
                    row=0,column=col,padx=5,pady=5,sticky='nw')
        actions=ctk.CTkFrame(row,fg_color='transparent');actions.grid(row=0,column=3,padx=5,sticky='w')
        for text,increase in (('-',False),('+',True)):
            ctk.CTkButton(actions,text=text,width=38,height=28,
                command=lambda category=data['type'],up=increase:self._map_region_change(category,up)).pack(side='left',padx=2)
        ctk.CTkButton(
            actions, text='Delete', width=72, height=28,
            fg_color=PopupTemplate.DANGER_BUTTON_FG_COLOR,
            hover_color=PopupTemplate.DANGER_BUTTON_HOVER_COLOR,
            command=lambda category=data['type']: self._map_region_delete(category),
        ).pack(side='left',padx=(6,2))

    def _map_region_delete_status_begin(self, category):
        existing = getattr(self, '_region_delete_status', None)
        if StatusWindowTemplate.exists(existing):
            StatusWindowTemplate.update(
                existing,
                text=f"Deleting all '{category}' objects in selected area...",
                fraction=None,
            )
            return existing
        owner = getattr(self, '_region_window', None)
        if owner is None or not owner.winfo_exists():
            owner = self.object_configuration_map_window or self
        status = StatusWindowTemplate.create(
            owner,
            text=f"Deleting all '{category}' objects in selected area...",
            title='Delete Objects',
            heading='Delete Objects',
            progress=True,
            fraction=None,
            modal=False,
            topmost=True,
            force_paint=True,
        )
        self._region_delete_status = status
        return status

    def _map_region_delete_status_close(self, delay_ms=250):
        status = getattr(self, '_region_delete_status', None)
        if not StatusWindowTemplate.exists(status):
            self._region_delete_status = None
            return

        def close_status():
            current = getattr(self, '_region_delete_status', None)
            if StatusWindowTemplate.exists(current):
                StatusWindowTemplate.close(current)
            self._region_delete_status = None

        self.after(delay_ms, close_status)

    def _map_region_delete(self, category):
        if getattr(self, '_region_delete_start_pending', False) or self._tmc_ram_is_busy():
            return
        self._region_delete_start_pending = True
        self._map_region_delete_status_begin(category)
        # Return to Tk first so the status window is painted before any category
        # preparation or worker startup takes place.
        self.after(75, lambda: self._map_region_delete_start(category))

    def _map_region_delete_start(self, category):
        self._region_delete_start_pending = False
        if not StatusWindowTemplate.exists(getattr(self, '_region_delete_status', None)):
            return
        self._map_region_change(category, False, percent_override=100.0)

    def _map_region_change(self,category,increase,percent_override=None):
        is_delete = percent_override is not None and float(percent_override) == 100.0 and not increase
        try:
            cache,session=self._map_session_current()
            percent=(float(percent_override) if percent_override is not None else float(self._region_amount.get().strip().replace(',','.')))
            if not math.isfinite(percent) or not 0 < percent <= 100:
                raise ValueError('Density (%) must be greater than 0 and at most 100.')
        except ValueError as exc:
            if is_delete:
                self._map_region_delete_status_close(delay_ms=150)
            messagebox.showerror('Selected Area',str(exc),parent=self._region_window)
            return
        area=self._region_area;bounds=self.object_configuration_map_bounds
        categories=self._map_region_categories(session,cache)
        def work(progress):
            current=session if session is not None else ObjectMapSession(cache)
            visible_categories={name for name,visible in self.object_configuration_map_category_visible.items() if visible}
            result=change_region_count(current,area,categories,category,increase,bounds,progress,percent=percent,visible_categories=visible_categories)
            return result,'region',self._map_preview_points(result),area,region_entries(result,area,categories,visible_categories)
        started = self._tmc_ram_begin('RD3D Map Edit',work)
        if is_delete and not started:
            self._map_region_delete_status_close(delay_ms=150)

    def _map_region_refresh(self,area,grouped):
        window=getattr(self,'_region_window',None)
        if window is None or not window.winfo_exists() or area!=self._region_area:return
        def format_indices(entries, per_line=20):
            values = [str(value) for value in sorted({index for _, index in entries})]
            return '\n'.join(
                ', '.join(values[start:start + per_line])
                for start in range(0, len(values), per_line)
            )

        rows=[dict(type=category,indices=format_indices(entries),count=len(entries))
              for category,entries in sorted(grouped.items(),key=lambda item:item[0].casefold())]
        body_font=ctk.CTkFont(size=TemplateTable.BODY_FONT_SIZE)
        header_font=ctk.CTkFont(size=TemplateTable.HEADER_FONT_SIZE,weight=TemplateTable.HEADER_FONT_WEIGHT)
        def measured(key,title):
            values = []
            for row in rows:
                text = str(row[key])
                # Multi-line values must be measured line by line. Measuring the
                # complete string makes Tk treat all wrapped indices as one line.
                values.extend(text.splitlines() or [''])
            longest = max((body_font.measure(value) for value in values), default=0)
            return math.ceil(max(longest, header_font.measure(title))) + 12
        columns=(TableColumn('type','Category',width=measured('type','Category'),anchor='w'),
            TableColumn('indices','Indices',width=min(360, measured('indices','Indices')),anchor='w'),
            TableColumn('count','Count',width=measured('count','Count'),anchor='w'),
            TableColumn('action','Change Density',width=max(210,math.ceil(header_font.measure('Change Density'))+12),anchor='w'))
        table=self._region_table
        table.columns=columns
        for widget in table.header.winfo_children():widget.destroy()
        for col,column in enumerate(columns):
            table.header.grid_columnconfigure(col,weight=0,minsize=column.width+2*TemplateTable.HEADER_PADX)
        table._build_header()
        table.set_rows(rows)
        if StatusWindowTemplate.exists(getattr(self, '_region_delete_status', None)):
            StatusWindowTemplate.update(
                self._region_delete_status,
                text='Delete completed. Updating selected area...',
                fraction=1.0,
            )
            self._map_region_delete_status_close(delay_ms=300)
        self._region_info.set(f'{sum(len(v) for v in grouped.values())} objects in selected area. '
            f'Each - / + changes the category by {self._region_amount.get().strip() or "0"}%. Preview only; use Object Map Save to write changes.')
