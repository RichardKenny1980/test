"""The build grid used by open and maze levels.

Open levels keep a fixed road, but turrets can go on any free cell beside it. Maze levels have no
road at all: ground enemies walk the shortest route through whatever the player has built, so the
player makes the path. A turret may never seal the route completely.
"""
from collections import deque

CELL = 20  # one turret per cell; the 640x280 map is 32 x 14 cells
NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class Grid:
    def __init__(self, cols, rows, origin=(0, 0), rocks=()):
        self.cols, self.rows = cols, rows
        self.ox, self.oy = origin
        self.rocks = {tuple(c) for c in rocks}  # cells nothing can walk through or build on

    def inside(self, cell):
        c, r = cell
        return 0 <= c < self.cols and 0 <= r < self.rows

    def center(self, cell):
        c, r = cell
        return self.ox + c * CELL + CELL / 2, self.oy + r * CELL + CELL / 2

    def cell_at(self, x, y):
        """The cell under a point, clamped onto the grid (enemies walk in from just off the edge)."""
        c = int((x - self.ox) // CELL)
        r = int((y - self.oy) // CELL)
        return min(max(c, 0), self.cols - 1), min(max(r, 0), self.rows - 1)

    def rect(self, cell):
        c, r = cell
        return self.ox + c * CELL, self.oy + r * CELL, CELL, CELL

    def cells(self):
        return [(c, r) for r in range(self.rows) for c in range(self.cols)]

    def distances(self, goal, walls):
        """Steps from every reachable cell to `goal`, walking around `walls` and rocks."""
        dist = {goal: 0}
        queue = deque([goal])
        while queue:
            cell = queue.popleft()
            for dc, dr in NEIGHBOURS:
                nxt = (cell[0] + dc, cell[1] + dr)
                if nxt in dist or not self.inside(nxt) or nxt in walls or nxt in self.rocks:
                    continue
                dist[nxt] = dist[cell] + 1
                queue.append(nxt)
        return dist

    def route(self, start, dist):
        """Cells from `start` to the goal, stepping downhill on a distance map. None if cut off.
        Ties prefer going straight, so routes have few corners."""
        if start not in dist:
            return None
        cells, cell, heading = [start], start, None
        while dist[cell] > 0:
            options = [(cell[0] + dc, cell[1] + dr) for dc, dr in NEIGHBOURS]
            options = [n for n in options if dist.get(n) == dist[cell] - 1]
            if heading is not None:
                options.sort(key=lambda n: (n[0] - cell[0], n[1] - cell[1]) != heading)
            nxt = options[0]
            heading = (nxt[0] - cell[0], nxt[1] - cell[1])
            cells.append(nxt)
            cell = nxt
        return cells

    def points(self, cells):
        """Cell centres along a route, keeping only the corners."""
        pts = [self.center(c) for c in cells]
        out = pts[:1]
        for prev, cur, nxt in zip(pts, pts[1:], pts[2:]):
            if (cur[0] - prev[0]) * (nxt[1] - cur[1]) != (cur[1] - prev[1]) * (nxt[0] - cur[0]):
                out.append(cur)
        if len(pts) > 1:
            out.append(pts[-1])
        return out
