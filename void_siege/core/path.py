import math


class Path:
    """A polyline that enemies walk along, addressed by distance travelled."""

    def __init__(self, points):
        self.points = [tuple(map(float, p)) for p in points]
        self.cumulative = [0.0]
        for (x1, y1), (x2, y2) in zip(self.points, self.points[1:]):
            self.cumulative.append(self.cumulative[-1] + math.hypot(x2 - x1, y2 - y1))
        self.length = self.cumulative[-1]

    def position(self, distance):
        """Return (x, y, heading_radians) at `distance` along the path."""
        distance = max(0.0, min(distance, self.length))
        for i in range(len(self.points) - 1):
            seg_start, seg_end = self.cumulative[i], self.cumulative[i + 1]
            if distance <= seg_end or i == len(self.points) - 2:
                (x1, y1), (x2, y2) = self.points[i], self.points[i + 1]
                seg_len = seg_end - seg_start or 1.0
                t = (distance - seg_start) / seg_len
                return x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, math.atan2(y2 - y1, x2 - x1)
        x, y = self.points[-1]
        return x, y, 0.0

    def distance_to(self, x, y):
        """Shortest distance from a point to the path's centre line."""
        best = math.inf
        for (x1, y1), (x2, y2) in zip(self.points, self.points[1:]):
            dx, dy = x2 - x1, y2 - y1
            seg_sq = dx * dx + dy * dy
            t = 0.0 if seg_sq == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / seg_sq))
            best = min(best, math.hypot(x - (x1 + dx * t), y - (y1 + dy * t)))
        return best
