"""Object Map placement: shared picker UI and worker-only XML insertion."""
from __future__ import annotations

from app.functions.function_custom_content import (
    get_combined_categories,
    get_combined_object_database,
    get_combined_regions,
    get_category_for_object,
    get_regions_for_category,
    get_regions_for_object,
    display_category,
    display_object,
    display_regions,
)
import copy
import math
import random
import tkinter as tk
from pathlib import Path
import customtkinter as ctk
from tkinter import messagebox
from app.templates.template_popup import PopupTemplate
from app.templates.template_statuswindow import StatusWindowTemplate
from app.templates.template_treeview import TreeviewTemplate
from app.templates.template_table import TemplateTable, TableColumn
from app.templates.template_category_picker import CategoryPickerTemplate
from app.templates.template_map_view import MapViewTemplate
from app.functions.function_density import DensitySession, child, position, local_tag, usage_counts
from app.database.database_props import RD3D_OBJECT_DATABASE
from app.config.config_rd3d import RD3D_REGIONS, rd3d_regions_for_object


def world_from_click(x, y, width, height, bounds, zoom, pan_x, pan_y, margin):
    lo, hi, bottom, top = bounds
    scale = min((width-2*margin)/(hi-lo), (height-2*margin)/(top-bottom))*zoom
    if scale <= 0:
        raise ValueError('The map viewport is too small.')
    left=(width-(hi-lo)*scale)/2+pan_x
    upper=(height-(top-bottom)*scale)/2+pan_y
    wx=lo+(x-left)/scale
    wz=top-(y-upper)/scale
    if not lo <= wx <= hi or not bottom <= wz <= top:
        raise ValueError('Click inside the playable map area.')
    return wx,wz





class ObjectMapSession(DensitySession):
    """One unsaved document for placement, deletion, density and Restore."""
    def fork(self):
        other=copy.copy(self)
        other.tree=copy.deepcopy(self.tree)
        other.usage=list(self.usage)
        return other

    def paths(self):
        grid=next(n for n in self.tree.getroot().iter() if local_tag(n)=='PropGrid')
        return [(n.text or '').strip() for n in child(grid,'FileNames')]

    def resolve_instance_ordinal(self, index, position_text):
        """Resolve a rendered map point to its exact instance ordinal."""
        grid = next(n for n in self.tree.getroot().iter() if local_tag(n) == 'PropGrid')
        instances = child(grid, 'Instances')
        if instances is None:
            return None
        return next((
            ordinal for ordinal, node in enumerate(instances)
            if child(node, 'Index') is not None
            and (child(node, 'Index').text or '').strip() == str(index)
            and child(node, 'Position') is not None
            and (child(node, 'Position').text or '').strip() == position_text
        ), None)

    def move_instance(self, ordinal, x, z):
        grid=next(n for n in self.tree.getroot().iter() if local_tag(n)=='PropGrid')
        instances=child(grid,'Instances')
        if not 0<=ordinal<len(instances): raise ValueError('The selected object no longer exists.')
        samples=[position(n) for i,n in enumerate(instances) if i!=ordinal and position(n) is not None]
        nearby=sorted(samples,key=lambda q:(q[0]-x)**2+(q[2]-z)**2)[:8]
        y=(sum(q[1]/max(((q[0]-x)**2+(q[2]-z)**2),.01) for q in nearby)/
           sum(1/max(((q[0]-x)**2+(q[2]-z)**2),.01) for q in nearby)) if nearby else 0.0
        node=instances[ordinal]
        pos=child(node,'Position')
        if pos is None: raise ValueError('The selected object has no Position node.')
        pos.text=f'{x:.8g} {y:.8g} {z:.8g}'
        self.dirty=True
        return y

    def delete_instance(self, ordinal):
        grid=next(n for n in self.tree.getroot().iter() if local_tag(n)=='PropGrid')
        instances=child(grid,'Instances')
        if not 0<=ordinal<len(instances):
            raise ValueError('The selected object no longer exists.')
        instances.remove(instances[ordinal])
        self.usage=usage_counts(self.tree)
        self.dirty=True

    def delete_instances(self, ordinals):
        """Delete multiple instances in one pass and rebuild usage only once."""
        grid = next(n for n in self.tree.getroot().iter() if local_tag(n) == 'PropGrid')
        instances = child(grid, 'Instances')
        if instances is None:
            raise ValueError('Missing RD3D Instances container.')
        unique = sorted({int(value) for value in ordinals}, reverse=True)
        if not unique:
            return 0
        if unique[0] >= len(instances) or unique[-1] < 0:
            raise ValueError('At least one selected object no longer exists.')
        for ordinal in unique:
            instances.remove(instances[ordinal])
        self.usage = usage_counts(self.tree)
        self.dirty = True
        return len(unique)

    def save(self, progress):
        values=self.paths()
        super().save(progress)
        self.cache.values=values
        self.cache.original_values=list(self.cache.original_values)+values[len(self.cache.original_values):]


def preview_placement(session, paths, count, center, bounds, progress, rng=None, area=None, polygon=None):
    """Create a new preview. No cache mutation and no disk writes."""
    if not paths or not isinstance(count,int) or not 1<=count<=10000:
        raise ValueError('Choose an object and a count from 1 to 10000.')
    rng=rng or random.Random()
    result=session.fork()
    grid=next(n for n in result.tree.getroot().iter() if local_tag(n)=='PropGrid')
    names,instances=child(grid,'FileNames'),child(grid,'Instances')
    if names is None or instances is None:raise ValueError('Missing FileNames or Instances.')
    candidates=[(n,position(n)) for n in instances if position(n) is not None]
    if not candidates:raise ValueError('No nearby object positions are available.')
    x,z=center;lo,hi,bottom,top=bounds
    if not lo<=x<=hi or not bottom<=z<=top:raise ValueError('Click inside PlayableArea.')
    if area is not None:
        ax,bx,az,bz=area
        if not lo<=ax<bx<=hi or not bottom<=az<bz<=top:
            raise ValueError('Invalid selected area.')
        # One jittered sample per tile spreads the batch across the rectangle.
        columns=max(1,min(count,math.ceil(math.sqrt(count*(bx-ax)/(bz-az)))))
        rows=math.ceil(count/columns)
        tiles=[(col,row) for row in range(rows) for col in range(columns)]
        # Select tiles spread over the full area even when rows*columns > count.
        tiles=[tiles[min(len(tiles)-1,int((i+.5)*len(tiles)/count))] for i in range(count)]
        rng.shuffle(tiles)
    neighbors=sorted(candidates,key=lambda pair:(pair[1][0]-x)**2+(pair[1][2]-z)**2)[:12]
    # Median local nearest-neighbor distance is robust against distant pairs.
    distances=[]
    for _,p in neighbors:
        nearby=[math.hypot(p[0]-q[0],p[2]-q[2]) for _,q in neighbors
                if (p[0],p[2])!=(q[0],q[2])]
        if nearby:distances.append(min(nearby))
    typical=sorted(distances)[len(distances)//2] if distances else min(hi-lo,top-bottom)/100
    # World-space center spacing, not an asset bounding-box collision test.
    minimum=max(typical*0.65, min(hi-lo,top-bottom)/1000, 0.05)
    radius=min(max(minimum*math.sqrt(count)*1.5,minimum*2),min(hi-lo,top-bottom)/10)
    buckets={}
    def bucket(px,pz):return math.floor(px/minimum),math.floor(pz/minimum)
    def register(px,pz):buckets.setdefault(bucket(px,pz),[]).append((px,pz))
    for _,p in candidates:register(p[0],p[2])
    def spaced(px,pz):
        bx,bz=bucket(px,pz)
        for dx in (-1,0,1):
            for dz in (-1,0,1):
                for qx,qz in buckets.get((bx+dx,bz+dz),()):
                    if (px-qx)**2+(pz-qz)**2 < minimum**2:return False
        return True
    lookup={v.casefold():i for i,v in enumerate(result.paths())}
    indices=[]
    for path in paths[:count]:
        if path.casefold() not in lookup:
            node=names.makeelement(names[0].tag if len(names) else 'None', {});node.text=path
            node.tail=names[-1].tail if len(names) else '\n'
            lookup[path.casefold()]=len(names);names.append(node)
        indices.append(lookup[path.casefold()])
    occupied={p for _,p in candidates}
    for i in range(count):
        for attempt in range(1000):
            if area is not None:
                col,row=tiles[i]
                nx=ax+(col+rng.random())*(bx-ax)/columns
                nz=az+(row+rng.random())*(bz-az)/rows
                # If a tile is blocked, retry throughout the selected rectangle.
                if attempt>=250:
                    nx,nz=rng.uniform(ax,bx),rng.uniform(az,bz)
                if polygon and not MapViewTemplate.point_in_polygon(nx, nz, polygon):
                    continue
            elif count==1 and attempt==0:nx,nz=x,z
            else:
                angle=rng.random()*math.tau;r=radius*math.sqrt(rng.random())
                nx,nz=x+math.cos(angle)*r,z+math.sin(angle)*r
            nx,nz=round(nx,7),round(nz,7)
            if not lo<=nx<=hi or not bottom<=nz<=top or not spaced(nx,nz):continue
            if area is not None and not (ax<=nx<=bx and az<=nz<=bz):continue
            local=sorted(candidates if area is not None else neighbors,key=lambda pair:(pair[1][0]-nx)**2+(pair[1][2]-nz)**2)[:4]
            weights=[1/max((p[0]-nx)**2+(p[2]-nz)**2,1e-12) for _,p in local]
            y=sum(p[1]*weight for (_,p),weight in zip(local,weights))/sum(weights)
            new=round(nx,7),round(y,7),round(nz,7)
            if new not in occupied:break
        else:raise ValueError(
            f'Not enough space for {count} objects near this point with a minimum spacing of {minimum:.3f}. '
            'No objects were inserted. Choose fewer objects or a larger/different area.')
        occupied.add(new)
        register(new[0],new[2])
        node=copy.deepcopy(local[0][0]);child(node,'Index').text=str(indices[i%len(indices)])
        child(node,'Position').text=' '.join(format(v,'.7f').rstrip('0').rstrip('.').replace('.',',') if v else '0' for v in new)
        instances.append(node)
        if i%50==0:progress(i,count)
    result.usage=usage_counts(result.tree);result.dirty=True
    progress(count,count)
    return result

class PlaceObjectMixin:
    def _place_object_open(self,event,area=None):
        if not self._object_profiles_available(1):return 'break'
        if not self._load_object_configuration_table_1_data():
            messagebox.showinfo('Place Object','The XML cache is loading. Please try again after loading.')
            return 'break'
        cache=self.rd3d_ram_cache
        if any(row[2].get().strip()!=cache.values[row[0]] for row in self.object_configuration_table1_rows):
            messagebox.showwarning('Place Object','Save Objects Table 1 path edits before placing objects.')
            return 'break'
        canvas=self.object_configuration_map_canvas
        try:
            from app.templates.template_map_view import MapViewTemplate
            center=world_from_click(event.x,event.y,canvas.winfo_width(),canvas.winfo_height(),
                self.object_configuration_map_bounds,self.object_configuration_map_shared_zoom,
                self.object_configuration_map_shared_pan_x,self.object_configuration_map_shared_pan_y,MapViewTemplate.MAP_MARGIN)
        except ValueError as exc:
            messagebox.showerror('Place Object',str(exc));return 'break'
        old=getattr(self,'_place_window',None)
        if old is not None and old.winfo_exists():old.destroy()
        built=PopupTemplate.create_window(self.object_configuration_map_window,title='Place Object',heading='Place Object')
        window=self._place_window=built['window'];window.grid_columnconfigure(0,weight=1);window.grid_rowconfigure(4,weight=1)
        self._place_center=center;self._place_cache=cache;self._place_area=tuple(area) if area is not None else None;self._place_polygon=tuple(getattr(self,'_map_lasso_points',())) if len(getattr(self,'_map_lasso_points',()))>=3 else None
        self._place_mode='Category';self._place_filter=tk.StringVar(master=self);self._place_checked=set()
        buttons=ctk.CTkFrame(window,fg_color='transparent');buttons.grid(row=1,column=0,padx=18,pady=8,sticky='w')
        for mode in ('Category','Object'):
            ctk.CTkButton(buttons,text=mode,width=110,command=lambda mode=mode:self._place_switch_loading(mode)).pack(side='left',padx=(0,8))
        filter_row=ctk.CTkFrame(window,fg_color='transparent');filter_row.grid(row=2,column=0,padx=18,pady=(0,8),sticky='ew');filter_row.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(filter_row,text='Filter:').grid(row=0,column=0,padx=(0,8),sticky='w')
        ctk.CTkEntry(filter_row,textvariable=self._place_filter,placeholder_text='Filter Category or Object...').grid(row=0,column=1,sticky='ew')
        self._place_region=CategoryPickerTemplate.FILTER_ALL
        self._place_region_bar=ctk.CTkScrollableFrame(window,height=48,orientation='horizontal',fg_color='transparent');self._place_region_bar.grid(row=3,column=0,padx=18,pady=(0,8),sticky='ew')
        self._place_region_buttons={}
        for region in (CategoryPickerTemplate.FILTER_ALL,) + tuple(get_combined_regions(self.CONFIG_FILE)):
            button=ctk.CTkButton(self._place_region_bar,text=region,width=CategoryPickerTemplate.GROUP_BUTTON_WIDTH,height=PopupTemplate.BUTTON_HEIGHT,command=lambda value=region:self._place_set_region(value))
            button.pack(side='left',padx=(0,6),pady=2);self._place_region_buttons[region]=button
        self._place_body=ctk.CTkFrame(window,fg_color='transparent');self._place_body.grid(row=4,column=0,padx=18,pady=(0,12),sticky='nsew');self._place_body.grid_columnconfigure(0,weight=1);self._place_body.grid_rowconfigure(0,weight=1)
        self._place_filter.trace_add('write',lambda *_:self._place_filter_changed())
        self._place_set_region(CategoryPickerTemplate.FILTER_ALL)
        self._place_switch_loading('Category')
        return 'break'

    def _place_set_region(self,region):
        self._place_region=region
        for name,button in self._place_region_buttons.items():
            active=name==region
            button.configure(fg_color=('#1f6aa5' if active else PopupTemplate.BUTTON_FG_COLOR),hover_color=('#144870' if active else PopupTemplate.BUTTON_HOVER_COLOR))
        state=getattr(self,'_place_category_state',None)
        if state is not None:state['region']=region
        self._place_filter_changed()

    def _place_switch_loading(self,mode):
        window=getattr(self,'_place_window',None)
        if window is None or not window.winfo_exists():return
        status=None
        try:
            status=StatusWindowTemplate.create(window,text=f'Loading {mode}...',title='Loading',heading='Loading')
            self._place_switch(mode)
            window.update_idletasks()
        finally:
            if status is not None:StatusWindowTemplate.close(status)

    def _place_switch(self,mode):
        self._place_mode=mode
        for widget in self._place_body.winfo_children():widget.destroy()
        self._place_body.grid_rowconfigure(0,weight=1)
        table_frame=ctk.CTkFrame(self._place_body,fg_color='transparent')
        table_frame.grid(row=0,column=0,sticky='nsew');table_frame.grid_rowconfigure(0,weight=1);table_frame.grid_columnconfigure(0,weight=1)
        self._place_checked = set()
        if mode=='Category':
            columns=('checked','category','variations','regions')
            headings={'checked':'Select','category':'Category','variations':'Variations','regions':'Regions'}
            min_widths={'checked':60,'category':90,'variations':75,'regions':90}
            max_widths={'checked':80,'category':520,'variations':140,'regions':1200}
        else:
            columns=('checked','category','object','regions')
            headings={'checked':'Select','category':'Category','object':'Object','regions':'Regions'}
            min_widths={'checked':60,'category':90,'object':160,'regions':90}
            max_widths={'checked':80,'category':520,'object':2400,'regions':1200}
        widgets=TreeviewTemplate.create(
            table_frame, columns=columns, headings=headings,
            min_widths=min_widths, max_widths=max_widths, stretch=(),
            sortable=True, dynamic_width=True, width_padding=24,
            selectable_cells=False, selectmode='extended',
        )
        self._place_tree=widgets['tree'];self._place_tree_rows={}
        self._place_tree.bind('<Button-1>', self._place_toggle_checked, add='+')
        ctk.CTkButton(self._place_body,text='Select',width=130,command=self._place_select).grid(row=1,column=0,pady=(10,0))
        self._place_filter_changed()

    def _place_filter_changed(self):
        tree=getattr(self,'_place_tree',None)
        if tree is None or not tree.winfo_exists():return
        selected=tree.selection();selected_key=self._place_tree_rows.get(selected[0]) if selected else None
        tree.delete(*tree.get_children());self._place_tree_rows={}
        terms=self._place_filter.get().casefold().split()
        if self._place_mode=='Category':
            rows=[]
            for item in self._object_configuration_database_categories():
                if isinstance(item,dict):
                    category=str(item.get('category','')).strip();variations=int(item.get('variations',0) or 0)
                    regions=tuple(str(value).strip() for value in item.get('regions',()) if str(value).strip());display_cat=str(item.get('display_category',category));display_regs=tuple(item.get('display_regions',regions))
                else:
                    category=str(item[0]).strip();variations=int(item[1]) if len(item)>1 else 0;regions=tuple(item[2]) if len(item)>2 else ()
                if not category:continue
                if self._place_region!=CategoryPickerTemplate.FILTER_ALL and self._place_region not in regions:continue
                region_text=', '.join(display_regs if isinstance(item,dict) else regions)
                shown_category=display_cat if isinstance(item,dict) else category
                if all(term in (shown_category+' '+region_text).casefold() for term in terms):rows.append((category,shown_category,variations,region_text))
            rows.sort(key=lambda row:row[0].casefold())
            for category,shown_category,variations,regions in rows:
                tag='category_'+str(len(self._place_tree_rows));tree.tag_configure(tag,foreground=self._object_configuration_picker_color(category))
                iid=tree.insert('', 'end', values=('☑' if ('Category',category) in self._place_checked else '☐',shown_category,variations,regions),tags=(tag,));self._place_tree_rows[iid]=('Category',category)
        else:
            rows=[];seen=set()
            for _,path,_count in get_combined_object_database(self.CONFIG_FILE):
                if not path or path.casefold() in seen:continue
                seen.add(path.casefold());category=self._classify_object_configuration_path(path);regions=tuple(get_regions_for_object(path, self.CONFIG_FILE))
                if self._place_region!=CategoryPickerTemplate.FILTER_ALL and self._place_region not in regions:continue
                region_text=', '.join(display_regions(regions, self.CONFIG_FILE))
                shown_category=display_category(category, self.CONFIG_FILE)
                shown_path=display_object(path, self.CONFIG_FILE)
                if all(term in (shown_category+' '+shown_path+' '+region_text).casefold() for term in terms):rows.append((category,shown_category,path,shown_path,region_text))
            rows.sort(key=lambda row:(row[0].casefold(),row[2].casefold()))
            for category,shown_category,path,shown_path,regions in rows:
                tag='object_'+str(len(self._place_tree_rows));tree.tag_configure(tag,foreground=self._object_configuration_picker_color(category))
                iid=tree.insert('', 'end', values=('☑' if ('Object',path) in self._place_checked else '☐',shown_category,shown_path,regions),tags=(tag,));self._place_tree_rows[iid]=('Object',path)
        if selected_key is not None:
            for iid,value in self._place_tree_rows.items():
                if value==selected_key:tree.selection_set(iid);tree.focus(iid);tree.see(iid);break

    def _place_toggle_checked(self, event):
        tree = getattr(self, '_place_tree', None)
        if tree is None or tree.identify_region(event.x, event.y) != 'cell':
            return
        if tree.identify_column(event.x) != '#1':
            return
        item = tree.identify_row(event.y)
        key = self._place_tree_rows.get(item)
        if key is None:
            return 'break'
        if key in self._place_checked:
            self._place_checked.remove(key)
            mark = '☐'
        else:
            self._place_checked.add(key)
            mark = '☑'
        values = list(tree.item(item, 'values'))
        values[0] = mark
        tree.item(item, values=values)
        tree.selection_set(tuple(
            iid for iid, row_key in self._place_tree_rows.items()
            if row_key in self._place_checked
        ))
        return 'break'

    def _place_select(self):
        tree = getattr(self, '_place_tree', None)
        checked = [
            key for iid, key in self._place_tree_rows.items()
            if key in self._place_checked
        ]
        if not checked and tree is not None:
            checked = [self._place_tree_rows[iid] for iid in tree.selection()
                       if iid in self._place_tree_rows]
        if not checked:
            messagebox.showwarning(
                'Place Object', 'Check at least one entry in the table first.',
                parent=self._place_window,
            )
            return
        groups = []
        labels = []
        for kind, value in checked:
            paths = (self._object_configuration_database_paths(value)
                     if kind == 'Category' else [value])
            paths = tuple(path for path in paths if path)
            if paths:
                groups.append(paths)
                labels.append(value)
        if not groups:
            messagebox.showwarning(
                'Place Object', 'The checked entries contain no placeable objects.',
                parent=self._place_window,
            )
            return
        self._place_choose(groups, ', '.join(labels))

    def _place_choose(self,path_groups,label):
        if not self._object_profiles_available(1):return
        dialog=ctk.CTkInputDialog(title='Place Object',text=f'{label}\nHow many objects should be inserted? (1-10000)')
        value=dialog.get_input()
        if value is None:return
        try:
            count=int(value.strip())
            if not 1<=count<=10000:raise ValueError()
        except ValueError:
            messagebox.showerror('Place Object','Enter a whole number from 1 to 10000.',parent=self._place_window);return
        cache=self._place_cache
        if self.rd3d_ram_cache is not cache:
            messagebox.showerror('Place Object','The island cache changed. Reopen Place Object.');return
        if not self._object_profiles_available(1):return
        if any(row[2].get().strip()!=cache.values[row[0]] for row in self.object_configuration_table1_rows):
            messagebox.showwarning('Place Object','Save Objects Table 1 edits first.');return
        center=self._place_center;bounds=self.object_configuration_map_bounds
        try:
            cache,session=self._map_session_current()
        except ValueError as exc:
            messagebox.showerror('Place Object',str(exc));return
        groups=tuple(tuple(group) for group in path_groups if group)
        area=getattr(self,'_place_area',None);polygon=getattr(self,'_place_polygon',None)
        def work(progress):
            current=session if session is not None else ObjectMapSession(cache)
            rng=random.Random()
            # Round-robin categories gives each checked category either floor(n/k)
            # or ceil(n/k) objects. Each category then chooses a random path.
            chosen=[rng.choice(groups[index % len(groups)]) for index in range(count)]
            rng.shuffle(chosen)
            current=preview_placement(current,chosen,count,center,bounds,progress,rng=rng,area=area,polygon=polygon)
            return current,'place',self._map_preview_points(current)
        self._tmc_ram_begin('RD3D Map Edit',work)



    def _map_session_current(self):
        path = Path(self.rd3d_file_var.get().strip())
        cache = self.rd3d_ram_cache
        if cache is None or cache.path != path:
            if not path.is_file():
                raise ValueError("Please load an existing rd3d_original.xml file first.")
            # Object Map owns an RD3D editing session. Load its current island
            # cache directly instead of showing "Load the cache first".
            cache = Rd3dXmlRamCache(path).load(lambda _done, _total: None)
            self.rd3d_ram_cache = cache
            self.object_configuration_table1_rows = [
                (index, old, tk.StringVar(value=current), count)
                for index, (old, current, count) in enumerate(
                    zip(cache.original_values, cache.values, cache.usage)
                )
            ]
            self._render_object_configuration_table_1()
            self.status_var.set(
                f"Object Map cache loaded: {len(cache.values)} object paths."
            )
        if any(row[2].get().strip()!=cache.values[row[0]] for row in self.object_configuration_table1_rows):
            raise ValueError('Save Objects Table 1 path edits before editing map objects.')
        session=getattr(self,'_map_edit_session',None)
        if session is not None and session.cache is not cache:
            if session.dirty:raise ValueError('The cache changed while map edits were unsaved. Reopen the map.')
            session=None
        if session is not None and session.signature!=cache.signature:
            if session.dirty:raise ValueError('RD3D changed. Save or discard map edits before reloading.')
            session=None
        return cache,session

    def _map_preview_points(self,session):
        categories={i:self._classify_object_configuration_path(path) for i,path in enumerate(session.paths())}
        return session.map_points(categories)

    def _map_edit_run(self,action,ordinal=None):
        try:
            cache,session=self._map_session_current()
            def work(progress):
                current=session.fork() if session is not None else ObjectMapSession(cache)
                if action=='delete':current.delete_instance(ordinal)
                elif action=='restore':current.restore()
                elif action=='save':current.save(progress)
                progress(1,1)
                return current,action,self._map_preview_points(current)
            self._tmc_ram_begin('RD3D Map Edit',work)
        except (ValueError,IndexError) as exc:
            messagebox.showerror('Object Map',str(exc),parent=self.object_configuration_map_window)

    def _map_edit_complete(self,result):
        session,action,points=result[:3]
        if session.cache is not self.rd3d_ram_cache:return
        self._map_edit_session=session
        self._density_session=session
        self._density_cache=session.cache
        self.object_configuration_map_points=points
        self.object_configuration_map_file_names=session.paths()
        self.object_configuration_map_info_var.set(
            f'{len(points)} instances | ' + ('Unsaved object changes' if session.dirty else 'Saved object state')
            + ' | Right click: Add Object')
        for point in points:
            category=point[5]
            self.object_configuration_map_category_visible.setdefault(category,True)
            self.object_configuration_map_category_colors.setdefault(category,self._object_configuration_picker_color(category))
        self._rebuild_object_configuration_map_legend()
        self._schedule_object_configuration_map_redraw()
        if action=='save':
            cache=session.cache
            self.object_configuration_table1_rows=[(i,old,tk.StringVar(master=self,value=cache.values[i]),cache.usage[i])
                for i,old in enumerate(cache.original_values)]
            self._render_object_configuration_table_1()
        self._object_density_refresh()
        if len(result)==5:
            self._map_region_refresh(result[3],result[4])
        else:
            region_window=getattr(self,'_region_window',None)
            if region_window is not None and region_window.winfo_exists():
                region_window.destroy()
                self._region_window=None
        if action == 'delete-region':
            removed = result[3] if len(result) > 3 else 0
            self._map_selection_clear()
            text = (
                f'{removed} object(s) removed from the selected area in memory. '
                'Click Object Map Save to write changes.'
            )
        else:
            text=('Object changes saved to rd3d_patched.xml.' if action=='save' else
                  'Original objects restored in memory. Click Save to write changes.' if action=='restore' else
                  'Object changes updated in memory. Click Save to write changes.')
        self.status_var.set(text)
        self.tmc_ram_info.set(text)
        if action=='save':
            messagebox.showinfo(
                'Object Map',
                'The changes were saved successfully.',
                parent=self.object_configuration_map_window,
            )

    def _map_delete_at(self,event,hit=None):
        if not self._object_profiles_available(1):return True
        if hit is None:
            points=self.object_configuration_map_screen_points
            hit=min(points,key=lambda p:(p[0]-event.x)**2+(p[1]-event.y)**2,default=None)
            if hit is None or (hit[0]-event.x)**2+(hit[1]-event.y)**2>64:return False
        try:
            cache,session=self._map_session_current()
            # Screen point identifies the instance by Index + exact Position text.
            # For overlapping identical objects, delete one occurrence only.
            if not messagebox.askyesno('Remove Object',
                f'Remove this object?\nIndex: {hit[2]}\nPosition: {hit[6]}\n\nChanges remain unsaved until Save.',
                parent=self.object_configuration_map_window,default='no'):return True
            def work(progress):
                current=session.fork() if session is not None else ObjectMapSession(cache)
                grid=next(n for n in current.tree.getroot().iter() if local_tag(n)=='PropGrid')
                instances=child(grid,'Instances')
                ordinal=next((i for i,n in enumerate(instances)
                    if child(n,'Index') is not None and (child(n,'Index').text or '').strip()==str(hit[2])
                    and child(n,'Position') is not None and (child(n,'Position').text or '').strip()==hit[6]),None)
                if ordinal is None:raise ValueError('The selected object no longer exists.')
                current.delete_instance(ordinal);progress(1,1)
                return current,'delete',self._map_preview_points(current)
            if self._object_profiles_available(1):self._tmc_ram_begin('RD3D Map Edit',work)
        except ValueError as exc:messagebox.showerror('Object Map',str(exc))
        return True
