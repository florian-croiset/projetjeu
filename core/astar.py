# core/astar.py
# A* pathfinding adapted to Echo's 2D platformer.
#
# Nodes = tiles (tx, ty). The graph is implicit: for each node, neighbours
# are generated from game_map.is_solid(). Constraints:
# - Left / Right to an air tile        -> cost 1.0
# - Down to an air tile (free fall)    -> cost 0.8
# - Up to an air tile                  -> cost 1.6 x step, only
# if the tile under the current node is solid (jump from the ground).
# Multi-tile up to `jump_height`; all intermediate tiles
# must be air.
#
# Heuristic: Manhattan (admissible - smallest edge = 0.8).
#
# If the goal is not reached within `max_iter` expansions, the "best effort"
# is returned: the path rebuilt towards the visited node whose heuristic
# to the goal is smallest. This keeps enemies from freezing when the
# player is out of reach.

import heapq


def heuristic(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _is_air(game_map, x, y):
    if 0 <= x < game_map.width_map and 0 <= y < game_map.height_map:
        return not game_map.is_solid(x, y)
    return False


def _start_valid(game_map, start):
    """If the start tile is solid (pathological case), try an adjacent air
    tile. Returns None if nothing is usable.
    """
    sx, sy = start
    if _is_air(game_map, sx, sy):
        return start
    for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1), (-1, -1), (1, -1)):
        nx, ny = sx + dx, sy + dy
        if _is_air(game_map, nx, ny):
            return (nx, ny)
    return None


def find_path(game_map, start, goal, max_iter=1500, height_jump=2):
    """A* on the tilemap. Returns a list [(tx, ty), ...] (full path from the
    start to the goal) or [] if nothing is usable.

    If the goal is unreachable but some nodes were visited, the partial path
    to the node closest to the goal is returned (best effort).
    """
    start = _start_valid(game_map, start)
    if start is None:
        return []
    if start == goal:
        return [start]

    width = game_map.width_map
    height = game_map.height_map
    is_solid = game_map.is_solid

    h0 = heuristic(start, goal)
    counter = 0
    open_heap = [(h0, counter, start)]
    g_score = {start: 0.0}
    parents = {start: None}
    visited = set()

    best_node = start
    best_h = h0

    def push(node, new_g, parent):
        nonlocal counter
        if node in visited:
            return
        if new_g < g_score.get(node, float('inf')):
            g_score[node] = new_g
            parents[node] = parent
            counter += 1
            heapq.heappush(
                open_heap,
                (new_g + heuristic(node, goal), counter, node),
            )

    while open_heap and len(visited) < max_iter:
        _, _, current = heapq.heappop(open_heap)
        if current in visited:
            continue
        visited.add(current)

        if current == goal:
            return _rebuild(parents, current)

        cx, cy = current
        g = g_score[current]
        on_ground = (cy + 1 < height and is_solid(cx, cy + 1))

        # Left / Right
        for ndx in (-1, 1):
            nx = cx + ndx
            if 0 <= nx < width and not is_solid(nx, cy):
                push((nx, cy), g + 1.0, current)

        # Down (fall)
        ny = cy + 1
        if ny < height and not is_solid(cx, ny):
            push((cx, ny), g + 0.8, current)

        # Up (jump) - only from the ground
        if on_ground:
            for step in range(1, height_jump + 1):
                ny = cy - step
                if ny < 0 or is_solid(cx, ny):
                    break
                push((cx, ny), g + 1.6 * step, current)

        h_current = heuristic(current, goal)
        if h_current < best_h:
            best_h = h_current
            best_node = current

    if best_node == start:
        return []
    return _rebuild(parents, best_node)


def _rebuild(parents, node):
    path = []
    n = node
    while n is not None:
        path.append(n)
        n = parents.get(n)
    path.reverse()
    return path
