"""Rooted, path-preserving topology for upright whole roots.

Crossings are geometric hypotheses: opposite arms are reconnected without a
biological junction. A remaining cycle is reported, never silently made a tree.
Pixel measurements remain available independently of physical calibration.
"""
from collections import defaultdict, deque
from dataclasses import dataclass
from itertools import combinations
import numpy as np
from scipy.ndimage import distance_transform_edt, map_coordinates
from skimage.morphology import skeletonize


@dataclass
class Edge:
    u: int
    v: int
    path: np.ndarray
    # Per-sample uncertainty for reconstructed identities in a shared bundle.
    # None means the ordinary observed graph, not proof of biological accuracy.
    inferred_mask: np.ndarray | None = None

    @property
    def length(self):
        # Five-pixel chords suppress the orientation bias of a digital staircase.
        # Endpoints (and hence junction locations) are retained exactly.
        ids = np.unique(np.r_[np.arange(0,len(self.path),5),len(self.path)-1])
        return float(np.linalg.norm(np.diff(self.path[ids], axis=0), axis=1).sum())

    def away(self, node):
        return self.path if node == self.u else self.path[::-1]

    def other(self, node):
        return self.v if node == self.u else self.u


def adjacency(edges):
    adj = defaultdict(list)
    for k, e in edges.items():
        adj[e.u].append(k)
        adj[e.v].append(k)
    return adj


def direction(path, reach=20):
    dist = np.r_[0., np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
    a = int(np.searchsorted(dist, min(reach * .25, dist[-1] * .2)))
    b = min(len(path)-1, int(np.searchsorted(dist, min(reach, dist[-1]))))
    vec = path[b] - path[a]
    return vec / max(np.linalg.norm(vec), 1e-9)


def angle(a, b):
    return float(np.degrees(np.arccos(np.clip(np.dot(a, b), -1, 1))))


def crown_axis_convergence(edges,coords,radius,base):
    """A fan converges at the root base, unlike a true branch below a stem."""
    adj=adjacency(edges)
    if base not in adj or len(adj[base])!=1:return None
    stem=edges[adj[base][0]];junction=stem.other(base)
    # A thick fan can skeletonize into several nearby junction pixels. Collect
    # its short central links before fitting the exiting axes (rotation stable).
    if len(adj[junction])<3:return None
    stem_width=max(2.,2*float(np.median(radius[tuple(stem.path.astype(int).T)])))
    group={junction};pending=[junction]
    while pending:
        n=pending.pop()
        for i in adj[n]:
            e=edges[i];m=e.other(n)
            if m in group or m==base or len(adj[m])<3:continue
            if e.length<=1.5*stem_width and np.linalg.norm(coords[m]-coords[base])<=3*stem_width:
                group.add(m);pending.append(m)
    outgoing=[(i,n) for n in group for i in adj[n]
              if i!=adj[base][0] and edges[i].other(n) not in group]
    if len(outgoing)<2:return None
    normals=[];offsets=[];widths=[]
    for i,n in outgoing:
        path=edges[i].away(n)
        if len(path)<4:return None
        sample=path[min(12,len(path)-1):min(35,len(path))].astype(int)
        width=2*float(np.median(radius[tuple(sample.T)]))
        first=min(len(path)-2,max(2,int(2*width)))
        part=path[first:min(len(path),first+max(12,int(4*width)))]
        d=direction(part,reach=max(12,4*width));normal=np.array([-d[1],d[0]])
        normals.append(normal);offsets.append(np.dot(normal,part.mean(axis=0)));widths.append(width)
    center,_,rank,_=np.linalg.lstsq(normals,offsets,rcond=None)
    width=max(2.,float(np.median(widths)))
    if rank!=2 or np.linalg.norm(center-coords[base])>width or stem.length>3*width:return None
    residual=np.max(np.abs(np.array(normals)@center-offsets))
    if residual>width*.5:return None
    return center,np.array([coords[n] for n in group]),width


def contract_degree_two(edges, protected=()):
    while True:
        adj = adjacency(edges)
        found = next((n for n, ids in adj.items() if len(ids) == 2
                      and ids[0] != ids[1] and n not in protected), None)
        if found is None:
            return
        i, j = adj[found]
        a, b = edges.pop(i), edges.pop(j)
        edges[i] = Edge(a.other(found), b.other(found),
                        np.vstack((a.away(found)[::-1], b.away(found)[1:])))


def consolidate_junction_pixels(edges, coords):
    """Collapse pixel-scale junction blobs before interpreting their degree.

    Skan may retain triangles and one-pixel leaves inside a thick junction.
    This is a raster cleanup (3 pixels), not a physical crossing threshold.
    """
    adj = adjacency(edges)
    links = defaultdict(set)
    for e in edges.values():
        if len(adj[e.u]) >= 3 and len(adj[e.v]) >= 3 and e.length <= 3.5:
            links[e.u].add(e.v)
            links[e.v].add(e.u)
    seen = set()
    for seed in sorted(links):
        if seed in seen:
            continue
        group, stack = set(), [seed]
        while stack:
            n = stack.pop()
            if n not in group:
                group.add(n)
                stack.extend(links[n]-group)
        seen |= group
        center = np.mean([coords[n] for n in group],axis=0)
        coords[seed] = center
        for i,e in list(edges.items()):
            if e.u in group and e.v in group:
                del edges[i]
            elif e.u in group:
                edges[i] = Edge(seed,e.v,np.vstack((center,e.path[1:])))
            elif e.v in group:
                edges[i] = Edge(e.u,seed,np.vstack((e.path[:-1],center)))
    adj = adjacency(edges)
    for i,e in list(edges.items()):
        if e.length <= 2 and min(len(adj[e.u]),len(adj[e.v])) == 1 and max(len(adj[e.u]),len(adj[e.v])) >= 3:
            del edges[i]
    contract_degree_two(edges)


def _component_count(edges):
    adj=adjacency(edges);remaining=set(adj);count=0
    while remaining:
        count+=1;stack=[remaining.pop()]
        while stack:
            n=stack.pop()
            for i in adj[n]:
                other=edges[i].other(n)
                if other in remaining:
                    remaining.remove(other);stack.append(other)
    return count


def primary_component_nodes(edges):
    """Choose the main root network, so an isolated speck cannot become its base."""
    adj=adjacency(edges);remaining=set(adj);groups=[]
    while remaining:
        nodes={remaining.pop()};pending=list(nodes);links=set()
        while pending:
            n=pending.pop()
            for i in adj[n]:
                links.add(i);m=edges[i].other(n)
                if m in remaining:remaining.remove(m);nodes.add(m);pending.append(m)
        groups.append((sum(len(edges[i].path) for i in links),nodes))
    return max(groups,key=lambda item:item[0])[1] if groups else set()


def proximal_node(edges,coords,root_direction):
    candidates=primary_component_nodes(edges)
    if not candidates:return None
    axis=0 if root_direction in ('top','bottom','none') else 1
    sign=-1 if root_direction in ('bottom','right') else 1
    return min(candidates,key=lambda n:(sign*coords[n][axis],coords[n][1-axis]))


def possible_crop_endpoints(mask,tip_coords):
    """Flag aligned endpoints on an inset image frame; never delete them."""
    points=np.asarray(tip_coords,float)
    if len(points)<3:return []
    pixels=np.argwhere(mask)
    if not len(pixels):return []
    lo,hi=pixels.min(axis=0),pixels.max(axis=0);suspect=np.zeros(len(points),bool)
    for axis in (0,1):
        margins=[lo[axis],mask.shape[axis]-1-hi[axis]]
        if max(margins)>0.05*mask.shape[axis] or abs(margins[0]-margins[1])>2:continue
        low=np.abs(points[:,axis]-lo[axis])<=1.5
        high=np.abs(points[:,axis]-hi[axis])<=1.5
        if low.sum()+high.sum()>=3 and low.any() and high.any() and max(low.sum(),high.sum())>=2:
            suspect|=low|high
    return [tuple(p) for p in points[suspect]]


def resolve_crossings(edges, coords, radius, max_distance_px=None, protected=(),
                      preserve_components=False, allow_short_context=True):
    events = []
    arm_cache={}
    context_cache={};use_context=False
    def arm(i,n):
        e=edges[i];cached=arm_cache.get((i,n))
        if cached is None or cached[0] is not e:
            p=e.away(n)
            sample=p[min(12,len(p)-1):min(35,len(p))].astype(int)
            width=float(np.median(radius[sample[:,0],sample[:,1]]))*2
            cached=(e,p,width,{})
            arm_cache[i,n]=cached
        return cached
    def arm_direction(i,n,reach):
        _,p,_,directions=arm(i,n)
        if reach not in directions:directions[reach]=direction(p,reach)
        return directions[reach]
    def context_direction(i,n,reach,blocked,adj):
        """Continue a short arm only through unambiguous, near-straight exits."""
        key=(i,n,reach,tuple(blocked));old=context_cache.get(key)
        if old is not None:
            value,deps,neighbours=old
            if all(edges.get(j) is e for j,e in deps.items()) and all(tuple(adj.get(k,()))==v for k,v in neighbours.items()):return value
        e=edges[i];p=e.away(n);end=e.other(n);visited={i};deps={i:e};neighbours={}
        length=float(np.linalg.norm(np.diff(p,axis=0),axis=1).sum())
        for _ in range(8):
            if length>=reach or end in blocked:break
            neighbours[end]=tuple(adj[end])
            forward=direction(p[max(0,len(p)-12):],reach=12)
            choices=[]
            for j in adj[end]:
                if j in visited:continue
                other=edges[j];deps[j]=other
                if other.other(end) in blocked:continue
                q=other.away(end)
                if len(q)<3:continue
                choices.append((angle(forward,direction(q,reach=max(12.,reach-length))),j,q))
            choices.sort(key=lambda item:item[0])
            if not choices or choices[0][0]>35:break
            if len(choices)>1 and choices[1][0]-choices[0][0]<15:break
            _,j,q=choices[0];p=np.vstack((p,q[1:]));visited.add(j)
            length+=float(np.linalg.norm(np.diff(q,axis=0),axis=1).sum());end=edges[j].other(end)
        value=direction(p,reach)
        context_cache[key]=(value,deps,neighbours)
        return value
    # Re-evaluate after each splice, so a path can pass through several overlaps.
    while True:
        adj = adjacency(edges)
        candidates = []
        for n, ids in adj.items():
            if len(ids) == 4 and len(set(ids)) == 4:
                candidates.append((None, n, n, ids))
        for k, e in edges.items():
            if e.u != e.v and len(adj[e.u]) == len(adj[e.v]) == 3:
                if len(set(adj[e.u] + adj[e.v])) != 5:
                    continue
                ids = [i for n in (e.u, e.v) for i in adj[n] if i != k]
                candidates.append((k, e.u, e.v, ids))
        accepted = []
        for connector, u, v, ids in candidates:
            if u in protected or v in protected:
                continue
            nodes = [u, u, v, v] if connector is not None else [u]*4
            profiles=[arm(i,n) for i,n in zip(ids,nodes)]
            paths = [p[1] for p in profiles]
            if min(len(p) for p in paths) < 3:
                continue
            widths = [p[2] for p in profiles]
            width = max(2., float(np.median(widths)))
            reach = max(12., 4*width)
            dirs = [arm_direction(i,n,reach) for i,n in zip(ids,nodes)]
            if use_context:
                dirs=[context_direction(i,n,reach,(u,v),adj) for i,n in zip(ids,nodes)]
            pairings = [((0,2),(1,3)), ((0,3),(1,2))]
            if connector is None:
                pairings.append(((0,1),(2,3)))
            for pairing in pairings:
                deviations = [180-angle(dirs[a], dirs[b]) for a,b in pairing]
                if max(deviations) > 25:
                    continue
                crossing_angle = angle(dirs[pairing[0][0]], dirs[pairing[1][0]])
                crossing_angle = min(crossing_angle, 180-crossing_angle)
                if crossing_angle < 12:
                    continue
                if connector is not None:
                    length = edges[connector].length
                    # Acute crossings overlap over a longer distance, proportional
                    # to local root width / sin(crossing angle), not scanner DPI.
                    bound = 2.5*width / max(np.sin(np.radians(crossing_angle)), .2)
                    if max_distance_px is not None:
                        bound = min(bound, max_distance_px)
                    if length > bound:
                        continue
                accepted.append((sum(deviations), connector, u, v, ids, pairing))
        # More than four arms can be an ordinary crossing superposed on a
        # branch, or several roots sharing a contact. Split one well-supported
        # opposite pair, leaving all other arms and the junction intact.
        for n,ids in adj.items():
            if n in protected or not 5<=len(ids)<=8 or len(set(ids))!=len(ids):continue
            width=max(2.,float(np.median([arm(i,n)[2] for i in ids])))
            reach=max(12.,4*width)
            for a,b in combinations(ids,2):
                pa,pb=arm(a,n),arm(b,n)
                if min(len(pa[1]),len(pb[1]))<max(6,2*width):continue
                da,db=arm_direction(a,n,reach),arm_direction(b,n,reach)
                deviation=180-angle(da,db)
                if deviation>12 or max(pa[2],pb[2])>1.8*max(1.,min(pa[2],pb[2])):continue
                # Avoid peeling a parallel bundle: at least two remaining arms
                # must meet the proposed through-axis at an appreciable angle.
                transverse=sum(min(angle(da,arm_direction(i,n,reach)),180-angle(da,arm_direction(i,n,reach)))>20 for i in ids if i not in (a,b))
                if transverse<2:continue
                accepted.append((deviation+8,'multi',n,n,[a,b],None))
        if not accepted:
            if allow_short_context and not use_context:use_context=True;continue
            break
        before_components=_component_count(edges) if preserve_components else None
        for _,connector,u,v,ids,pairing in sorted(accepted,key=lambda x:x[0]):
            if connector=='multi':
                a,b=[edges[i] for i in ids]
                trial=edges.copy()
                for i in ids:del trial[i]
                trial[ids[0]]=Edge(a.other(u),b.other(u),np.vstack((a.away(u)[::-1],b.away(u)[1:])))
                if preserve_components and _component_count(trial)>before_components:continue
                edges.clear();edges.update(trial)
                point=tuple(coords[u])
                if point not in events:events.append(point)
                contract_degree_two(edges,protected)
                break
            nodes = [u,u,v,v] if connector is not None else [u]*4
            arms = [edges[i] for i in ids]
            link = edges[connector].away(u) if connector is not None else coords[u][None,:]
            trial=edges.copy()
            for i in ids:del trial[i]
            if connector is not None:del trial[connector]
            for i,(a,b) in zip(ids,pairing):
                pa,pb=arms[a].away(nodes[a]),arms[b].away(nodes[b])
                mid=link if nodes[a]==u else link[::-1]
                trial[i]=Edge(arms[a].other(nodes[a]),arms[b].other(nodes[b]),
                              np.vstack((pa[::-1],mid[1:],pb[1:])))
            if preserve_components and _component_count(trial)>before_components:
                continue
            edges.clear();edges.update(trial)
            point=tuple(np.mean(link,axis=0))
            if point not in events:events.append(point)
            contract_degree_two(edges,protected)
            break
        else:
            if allow_short_context and not use_context:use_context=True;continue
            break
    return events


def resolve_crown_region(edges, coords, box, root_direction, preserve_tips=False):
    """Explicit reviewed crown rectangle, not an inferred biological boundary.

    Reconnect each exiting root to the crown along the existing shortest path.
    Shared crown pixels may belong to several roots; this remains an estimate.
    """
    import heapq
    if len(box)!=4 or not np.all(np.isfinite(box)):
        raise ValueError("Crown rectangle requires four finite coordinates")
    r0,c0,r1,c1 = box
    if r0>r1 or c0>c1:
        raise ValueError("Crown rectangle coordinates are reversed")
    adj = adjacency(edges)
    group = {n for n in adj if r0<=coords[n][0]<=r1 and c0<=coords[n][1]<=c1}
    if not group:
        raise ValueError('Crown rectangle contains no graph nodes')
    axis = 0 if root_direction in ('top','bottom') else 1
    sign = -1 if root_direction in ('bottom','right') else 1
    base = min(group,key=lambda n:sign*coords[n][axis])
    dist, paths = {base:0.}, {base:coords[base][None,:]}
    queue = [(0.,base)]
    while queue:
        d,n = heapq.heappop(queue)
        if d != dist[n]:
            continue
        for i in adj[n]:
            e = edges[i]
            m = e.other(n)
            if m in group and d+e.length < dist.get(m,np.inf):
                dist[m] = d+e.length
                paths[m] = np.vstack((paths[n],e.away(n)[1:]))
                heapq.heappush(queue,(dist[m],m))
    if set(paths) != group:
        raise ValueError('Crown rectangle includes disconnected nodes')
    if preserve_tips and sum(e.u in group and e.v in group for e in edges.values())>=len(group):
        raise ValueError('Automatic crown region contains unresolved loops')
    for i,e in list(edges.items()):
        if e.u in group and e.v in group:
            tip=next((n for n in (e.u,e.v) if n!=base and len(adj[n])==1),None)
            if preserve_tips and tip is not None:
                edges[i]=Edge(base,tip,paths[tip])
            else:
                del edges[i]
        elif e.u in group:
            edges[i] = Edge(base,e.v,np.vstack((paths[e.u],e.path[1:])))
        elif e.v in group:
            edges[i] = Edge(e.u,base,np.vstack((e.path[:-1],paths[e.v][::-1])))
    return base


def extend_terminals(edges,coords,mask):
    """Extend a medial-axis endpoint to the foreground boundary along its axis."""
    adj = adjacency(edges)
    radius = distance_transform_edt(mask)
    for n,ids in adj.items():
        if len(ids) != 1:
            continue
        i=ids[0]; e=edges[i]; p=e.away(n)
        if len(p)<8:
            continue
        outward=-direction(p,reach=20.)
        start=p[0]
        cap=max(3.,3*radius[tuple(start.astype(int))])
        distances=np.arange(0,cap+.25,.25)
        pts=start+distances[:,None]*outward
        values=map_coordinates(mask.astype(float),pts.T,order=1,mode='constant',cval=0.)
        outside=np.flatnonzero(values<.5)
        if not len(outside) or outside[0]==0:
            continue
        k=outside[0]
        distance=distances[k-1]+.25*(values[k-1]-.5)/max(values[k-1]-values[k],1e-9)
        point=start+distance*outward
        coords[n]=point
        p=np.vstack((point,p))
        edges[i]=Edge(e.u,e.v,p if n==e.u else p[::-1])


def tree_metrics(edges, coords, base_node):
    adj = adjacency(edges)
    components = []
    remaining = set(adj)
    while remaining:
        seed = min(remaining)
        comp, stack = set(), [seed]
        while stack:
            n = stack.pop()
            if n in comp:
                continue
            comp.add(n)
            stack.extend(edges[i].other(n) for i in adj[n])
        remaining -= comp
        components.append(comp)
    comp = next((c for c in components if base_node in c), set())
    cycles = sum(len([i for i,e in edges.items() if e.u in c])-len(c)+1 for c in components)
    valid = bool(comp) and cycles == 0 and len(components) == 1
    result = dict(Strahler_Max_Order=np.nan, Strahler_Bifurcation_Ratio=np.nan,
                  Strahler_Length_Ratio=np.nan, Strahler_Orders=[],
                  Num_Components=len(components),
                  Largest_Component_Node_Fraction=max(map(len,components),default=0)/max(len(adj),1),
                  _TI=np.nan, _TI_altitude=np.nan, _TI_magnitude=np.nan)
    if not valid:
        return result, {}, {}, cycles
    parent = {base_node:None}
    order = [base_node]
    parent_edge = {}
    for n in order:
        for i in adj[n]:
            child = edges[i].other(n)
            if child not in parent:
                parent[child] = n
                parent_edge[child] = i
                order.append(child)
    children = defaultdict(list)
    for child,p in parent.items():
        if p is not None:
            children[p].append(child)
    levels, depth = {}, {base_node:0}
    for n in order:
        for c in children[n]:
            depth[c] = depth[n]+1
    for n in reversed(order):
        if n == base_node:
            continue
        values = [levels[parent_edge[c]] for c in children[n]]
        mx = max(values, default=1)
        levels[parent_edge[n]] = mx+1 if values.count(mx) >= 2 else mx
    # Count maximal same-order branches, not links cut by lower-order insertions.
    groups = defaultdict(list)
    unused = set(edges)
    while unused:
        seed = min(unused)
        level = levels[seed]
        stack, segment = [seed], set()
        while stack:
            i = stack.pop()
            if i in segment:
                continue
            segment.add(i)
            e = edges[i]
            stack.extend(j for n in (e.u,e.v) for j in adj[n]
                         if levels[j] == level and j not in segment
                         and parent_edge.get(n) in (i,j))
        unused -= segment
        groups[level].append(sum(edges[i].length for i in segment))
    details = [dict(order=k, count=len(v), total_length_px=sum(v), avg_length_px=np.mean(v))
               for k,v in sorted(groups.items())]
    rb = [len(groups[k])/len(groups[k+1]) for k in groups if k+1 in groups]
    rl = [np.mean(groups[k+1])/np.mean(groups[k]) for k in groups if k+1 in groups]
    tips = [n for n in comp if len(adj[n]) == 1 and n != base_node]
    altitude = max((depth[n] for n in tips), default=0)
    result.update(Strahler_Max_Order=max(levels.values(),default=0),
                  Strahler_Bifurcation_Ratio=float(np.mean(rb)) if rb else np.nan,
                  Strahler_Length_Ratio=float(np.mean(rl)) if rl else np.nan,
                  Strahler_Orders=details, _TI_altitude=altitude, _TI_magnitude=len(tips),
                  _TI=float(np.log(altitude)/np.log(len(tips))) if len(tips)>1 and altitude else np.nan)
    return result, levels, parent, cycles


def analyze_topology(skeleton, dpi=300, binary=None, base_rc=None,
                     root_direction='top', min_spur_mm=0., cross_merge_mm=None,
                     crown_box=None, crossing_context=True, root_model='general'):
    from skan import Skeleton, summarize
    if root_direction not in ('top','bottom','left','right','none'):
        raise ValueError('root_direction must be top/bottom/left/right/none')
    if root_model not in ('general', 'shared_crown'):
        raise ValueError('root_model must be general or shared_crown')
    if not np.isfinite(dpi) or dpi <= 0:
        raise ValueError('dpi must be positive')
    skel = skeletonize(np.asarray(skeleton, dtype=bool))
    mask = skel if binary is None else np.asarray(binary, dtype=bool)
    if mask.shape != skel.shape:
        raise ValueError('Binary and skeleton shapes differ')
    radius = distance_transform_edt(mask)
    edges, coords = {}, {}
    if skel.sum() >= 2:
        sk = Skeleton(skel)
        bd = summarize(sk, separator='-')
        coords = {n:p.astype(float) for n,p in enumerate(sk.coordinates)}
        edges = {int(i):Edge(int(r['node-id-src']),int(r['node-id-dst']),
                             sk.path_coordinates(int(i)).astype(float)) for i,r in bd.iterrows()}
    consolidate_junction_pixels(edges,coords)
    crown_source = 'manual_rectangle' if crown_box is not None else 'none'
    crown_base, crown_error = None, ''
    if crown_box is not None:
        try:
            crown_base = resolve_crown_region(edges,coords,crown_box,root_direction,
                                               preserve_tips=crown_source=='inferred_local_crown')
        except (ValueError, TypeError) as exc:
            if crown_source=='inferred_local_crown':
                crown_box=None;crown_source='none'
            else:
                crown_error = str(exc)
                root_direction = 'none'
                base_rc = None
    # Only explicit pruning. Short biological laterals are otherwise retained.
    if min_spur_mm > 0:
        adj = adjacency(edges)
        for i,e in list(edges.items()):
            if e.length < dpi*min_spur_mm/25.4 and sorted((len(adj[e.u]),len(adj[e.v])))[0] == 1 and max(len(adj[e.u]),len(adj[e.v]))>=3:
                del edges[i]
        contract_degree_two(edges)
    root_anchor=crown_base
    adj_before=adjacency(edges)
    if root_anchor is None and adj_before and root_direction!='none':
        if base_rc is not None:
            root_anchor=min(adj_before,key=lambda n:np.linalg.norm(coords[n]-base_rc))
        else:
            root_anchor=proximal_node(edges,coords,root_direction)
    crossings = resolve_crossings(edges,coords,radius,
                                  None if cross_merge_mm is None else dpi*cross_merge_mm/25.4,
                                  protected=(root_anchor,),
                                  preserve_components=root_direction!='none',
                                  allow_short_context=crossing_context)
    contract_degree_two(edges,protected=(crown_base,))
    # Medial axes of blunt ends contain short cap branches; their extent is
    # below the local radius. Record this raster-level pruning explicitly.
    raster_pruned = 0
    adj0=adjacency(edges)
    axis0=0 if root_direction in ('top','bottom','none') else 1
    sign0=-1 if root_direction in ('bottom','right') else 1
    proximal=root_anchor
    for i,e in list(edges.items()):
        leaf = e.u if len(adj0[e.u])==1 else (e.v if len(adj0[e.v])==1 else None)
        if leaf is not None and leaf != proximal and (len(adj0[e.other(leaf)])>=3 or e.other(leaf)==crown_base):
            junction=coords[e.other(leaf)].astype(int)
            if e.length < 1.5*radius[tuple(junction)]:
                del edges[i]
                raster_pruned += 1
    contract_degree_two(edges,protected=(crown_base,))
    if crown_base is None and base_rc is None and root_direction!='none' and not crown_error:
        fan=crown_axis_convergence(edges,coords,radius,root_anchor)
        if fan is not None:
            center,junctions,width=fan
            old_coord=coords[root_anchor].copy()
            lo=np.minimum(center,junctions.min(axis=0))-width*.5
            hi=np.maximum(center,junctions.max(axis=0))+width*.5
            candidate_box=(*lo,*hi)
            coords[root_anchor]=center
            try:
                crown_base=resolve_crown_region(edges,coords,candidate_box,root_direction,preserve_tips=True)
                crown_source='inferred_local_crown';crown_box=candidate_box
            except (ValueError,TypeError):
                coords[root_anchor]=old_coord
    if binary is not None:
        extend_terminals(edges,coords,mask)
    adj = adjacency(edges)
    base = None
    if adj and root_direction != 'none':
        if crown_base is not None:
            base = crown_base
        elif base_rc is not None:
            base = min(adj, key=lambda n:np.linalg.norm(coords[n]-base_rc))
        else:
            base=proximal_node(edges,coords,root_direction)
    observed_edges = edges
    reconstruction = dict(status='not_requested', model=root_model)
    if root_model == 'shared_crown':
        from root_crown import trace_shared_crown
        traced, reconstruction = trace_shared_crown(edges, coords, base)
        if traced is not None:
            edges = traced
            adj = adjacency(edges)
            crown_source = 'explicit_shared_crown_model'
    tip_nodes = [n for n in adj if len(adj[n]) == 1 and n != base]
    fork_nodes = [n for n in adj if len(adj[n]) >= 3 and n != base]
    st, levels, parent, cycles = tree_metrics(edges,coords,base)
    angles, angle_viz = [], []
    for n in fork_nodes:
        if n not in parent or parent[n] is None:
            continue
        incoming = next(i for i in adj[n] if edges[i].other(n) == parent[n])
        forward = -direction(edges[incoming].away(n))
        outgoing = [i for i in adj[n] if i != incoming]
        continuation = min(outgoing, key=lambda i:angle(forward,direction(edges[i].away(n))))
        for i in outgoing:
            if i == continuation:
                continue
            d = direction(edges[i].away(n))
            a = angle(forward,d)
            angles.append(a)
            angle_viz.append(dict(rc=tuple(coords[n]),dirs=[forward.tolist(),d.tolist()],angle=a))
    length = sum(e.length for e in edges.values())
    scale = 2.54/dpi
    for item in st['Strahler_Orders']:
        item['total_length_cm'] = item['total_length_px']*scale
        item['avg_length_cm'] = item['avg_length_px']*scale
    status = 'invalid_crown' if crown_error else ('ok' if parent else ('empty' if not edges else 'unresolved'))
    if reconstruction['status'] == 'applied':
        status = 'model_assumed'
    # Distinguish image junctions from established biological branch points.
    # Nodes on unresolved cycles and narrow bundle contacts need review.
    import networkx as nx
    network=nx.MultiGraph()
    network.add_edges_from((e.u,e.v,{'key_id':i}) for i,e in edges.items())
    bridges={frozenset(pair) for pair in nx.bridges(network)}
    cyclic_nodes={n for e in edges.values() if frozenset((e.u,e.v)) not in bridges for n in (e.u,e.v)}
    from root_crown import bundle_contact_candidates
    bundles=bundle_contact_candidates(edges,coords,radius,base) if parent else []
    bundle_ancestors={r['node'] for r in bundles}
    for node in list(bundle_ancestors):
        while node in parent and parent[node] is not None:
            node=parent[node];bundle_ancestors.add(node)
    uncertain_nodes=(cyclic_nodes|bundle_ancestors)&set(fork_nodes)
    primary=primary_component_nodes(edges)
    return dict(num_tips=len(tip_nodes), num_forks=len(fork_nodes),
                num_crossings=len(crossings), num_junctions=len(fork_nodes)+len(crossings),
                tip_coords=[tuple(coords[n]) for n in tip_nodes],
                fork_coords=[tuple(coords[n]) for n in fork_nodes], crossing_coords=crossings,
                base_coords=[] if base is None else [tuple(coords[base])],
                root_length_px=length, root_length_cm=length*scale,
                projected_length_px=sum(e.length for e in observed_edges.values()),
                root_model=root_model, reconstruction=reconstruction,
                num_root_paths=len(edges) if reconstruction['status']=='applied' else None,
                bundle_separation_coords=[tuple(r['rc']) for r in reconstruction.get('contacts',[])],
                avg_link_length_cm=length*scale/len(edges) if edges else 0.,
                avg_branch_angle=float(np.mean(angles)) if angles else np.nan,
                strahler=st, edges=[(e.u,e.v,e.length) for e in edges.values()],
                topology_status=status, topology_error=crown_error, cycle_rank=cycles,
                crown_source=crown_source, crown_box=crown_box,
                raster_pruned=raster_pruned,
                uncertain_junction_coords=[tuple(coords[n]) for n in sorted(uncertain_nodes)],
                num_uncertain_junctions=len(uncertain_nodes),
                bundle_contacts=bundles,
                fragment_tip_coords=[tuple(coords[n]) for n in tip_nodes if n not in primary],
                boundary_tip_coords=[tuple(coords[n]) for n in tip_nodes if np.any(coords[n]<1) or np.any(coords[n]>=np.array(mask.shape)-2)],
                possible_crop_tip_coords=possible_crop_endpoints(mask,[coords[n] for n in tip_nodes]),
                _angle_viz=angle_viz,
                _strahler_edge_viz=[(edges[i].path,k) for i,k in levels.items()],
                _resolved_edges=edges, _observed_edges=observed_edges)


def measure_paths(edges, binary, *, return_profiles=False):
    """Integrate local diameters, surface and volume along resolved paths.

    Use normal sections away from other centre-lines; interpolate obscured
    sections within each root. Entirely obscured links are flagged when no
    collinear measured continuation exists. Units are px, px², px³.
    """
    mask = np.asarray(binary,dtype=float)
    radius = distance_transform_edt(mask)
    from scipy.spatial import cKDTree
    profiles={}
    for key,e in edges.items():
        p = e.path
        if len(p)<2:
            continue
        idx = np.arange(len(p))
        tangent = p[np.minimum(idx+5,len(p)-1)]-p[np.maximum(idx-5,0)]
        norm = np.linalg.norm(tangent,axis=1)
        normal = np.column_stack((-tangent[:,1],tangent[:,0]))/np.maximum(norm[:,None],1e-9)
        widths = np.zeros(len(p))
        cap = max(3.,float(np.max(radius[p[:,0].astype(int),p[:,1].astype(int)]))*3)
        for sign in (-1,1):
            active = np.ones(len(p),dtype=bool)
            last = np.ones(len(p))
            dist = np.full(len(p),cap)
            for step in np.arange(.5,cap+.5,.5):
                ids = np.flatnonzero(active)
                if not len(ids):
                    break
                pts = p[ids]+sign*step*normal[ids]
                vals = map_coordinates(mask,pts.T,order=1,mode='constant',cval=0.)
                hit = vals<.5
                selected = ids[hit]
                dist[selected] = step-.5 + .5*(last[selected]-.5)/np.maximum(last[selected]-vals[hit],1e-9)
                active[selected] = False
                last[ids] = vals
            widths += dist
        arc=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
        inferred = np.zeros(len(p),bool) if e.inferred_mask is None else np.asarray(e.inferred_mask,bool)
        if inferred.shape != (len(p),):
            raise ValueError('Inferred path mask must match path samples.')
        candidates = (widths>0)&~inferred
        typical=float(np.median(widths[candidates])) if candidates.any() else float(np.median(widths))
        profiles[key]=dict(edge=e,p=p,widths=widths,arc=arc,inferred_path=inferred,
                           tangent=tangent/np.maximum(norm[:,None],1e-9),typical=typical)
    # A union mask is wider at contacts. Locate other centre-lines explicitly,
    # then interpolate each root's diameter from its own unobscured sections.
    keys=list(profiles)
    boxes={i:np.r_[v['p'].min(axis=0),v['p'].max(axis=0)] for i,v in profiles.items()}
    bounds=np.array([boxes[k] for k in keys])
    for key,v in profiles.items():
        p=v['p'];w=v['typical'];margin=max(5.,2*w)
        lo=p.min(axis=0)-margin;hi=p.max(axis=0)+margin
        points=[];other_widths=[]
        nearby=np.flatnonzero(np.all(bounds[:,2:]>=lo,axis=1)&np.all(bounds[:,:2]<=hi,axis=1))
        for index in nearby:
            j=keys[index]
            if j==key:continue
            q=profiles[j]['p'];inside=np.all((q>=lo)&(q<=hi),axis=1)
            if inside.any():
                points.append(q[inside])
                other_size=np.full(inside.sum(),profiles[j]['typical'])
                if v['edge'].inferred_mask is not None:
                    # Multiple identities may share the centre of a broad bundle.
                    # Their individual diameters understate its actual footprint.
                    occupied=2*map_coordinates(radius,q[inside].T,order=1,mode='nearest')
                    other_size=np.maximum(other_size,occupied)
                other_widths.append(other_size)
        safe=(v['widths']>0)&~v['inferred_path']&(v['arc']>=w*.5)&(v['arc'][-1]-v['arc']>=w*.5)
        if v['edge'].inferred_mask is not None:
            # Near a separating bundle, a normal ray can run into another root
            # through a raster-scale gap. An exclusive medial-axis section must
            # also agree with its distance to the nearest foreground boundary.
            # This is local geometry, not a constant-diameter cutoff.
            local_radius=map_coordinates(radius,p.T,order=1,mode='nearest')
            safe &= v['widths'] <= np.maximum(3.,2.8*local_radius)
        # At a sharp bend, a normal section can cut through the neighbouring
        # leg even though it is locally adjacent in arc length.
        before=np.searchsorted(v['arc'],np.maximum(0.,v['arc']-w))
        after=np.minimum(len(p)-1,np.searchsorted(v['arc'],v['arc']+w))
        safe &= np.einsum('ij,ij->i',v['tangent'][before],v['tangent'][after])>=np.cos(np.deg2rad(45))
        # A contracted edge may cross itself. Only its local arc neighbourhood
        # is the same section; distant arcs must also count as occluders.
        self_pairs=cKDTree(p).query_pairs(max(1.,1.2*w),output_type='ndarray')
        if len(self_pairs):
            distant=np.abs(v['arc'][self_pairs[:,0]]-v['arc'][self_pairs[:,1]])>max(2.,2.4*w)
            safe[self_pairs[distant].ravel()]=False
        if points:
            cloud=np.vstack(points);ow=np.concatenate(other_widths)
            distance,nearest=cKDTree(cloud).query(p)
            safe &= distance > .6*(w+ow[nearest])
        v['safe']=safe
        if safe.sum()>=3:
            # Median over only measured sections, never across an overlap.
            from scipy.ndimage import median_filter
            measured=median_filter(v['widths'][safe],size=min(31,int(safe.sum())//2*2+1),mode='nearest')
            v['estimate']=np.interp(v['arc'],v['arc'][safe],measured)
    # Short links can be entirely inside a contact. Transfer width only from
    # incident, nearly collinear measured segments, retaining the unmeasured flag.
    adj=adjacency(edges)
    for key,v in profiles.items():
        if 'estimate' in v:continue
        candidates=[];e=v['edge']
        # A different root in a bundle cannot supply this root's diameter.
        for n in ((e.u,e.v) if e.inferred_mask is None else ()):
            own=direction(e.away(n),reach=max(5.,2*v['typical']))
            for j in adj[n]:
                if j==key or j not in profiles or profiles[j]['safe'].sum()<3:continue
                other=profiles[j];deviation=180-angle(own,direction(other['edge'].away(n),reach=max(5.,2*other['typical'])))
                if deviation<25:
                    candidates.append((deviation,float(other['estimate'][0 if n==other['edge'].u else -1])))
        if candidates:
            candidates.sort();v['estimate']=np.full(len(v['p']),candidates[0][1]);v['inferred']=True
        else:
            v['estimate']=v['widths'];v['unresolved']=True
    length=surface=volume=width_sum=measured_length=unresolved_length=inferred_length=0.
    for v in profiles.values():
        e=v['edge'];d=(v['estimate'][:-1]+v['estimate'][1:])/2
        dl=np.diff(v['arc'])
        if dl.sum()>0:dl=dl*(e.length/dl.sum())
        length+=float(dl.sum());width_sum+=float(np.dot(d,dl))
        surface+=float(np.dot(np.pi*d,dl));volume+=float(np.dot(np.pi*d*d/4,dl))
        measured_length+=float(dl[v['safe'][:-1]&v['safe'][1:]].sum())
        inferred_length+=float(dl[v['inferred_path'][:-1]|v['inferred_path'][1:]].sum())
        if v.get('unresolved'):unresolved_length+=float(dl.sum())
    result = dict(length_px=length,diameter_px=width_sum/length if length else 0.,
                surface_px2=surface,volume_px3=volume,
                diameter_measured_fraction=measured_length/length if length else 0.,
                diameter_unresolved_fraction=unresolved_length/length if length else 0.,
                path_inferred_length_fraction=inferred_length/length if length else 0.)
    return (result, profiles) if return_profiles else result
