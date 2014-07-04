# -*- coding: utf-8 -*-

# Copyright (C) 2014 Osmo Salomaa
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Narration of routing maneuvers."""

import poor

__all__ = ("Narrative",)


class Maneuver:

    """A routing maneuver."""

    def __init__(self, **kwargs):
        """Initialize a :class:`Maneuver` instance."""
        self.icon = "alert"
        self.narrative = ""
        self.node = None
        self.passed = False
        self._visited_dist = 40000
        self.x = None
        self.y = None
        for name in set(kwargs) & set(dir(self)):
            setattr(self, name, kwargs[name])

    def set_visited(self, dist):
        """Set distance at which maneuver node has been visited."""
        if dist < self._visited_dist:
            self._visited_dist = dist
        # Setting these thresholds too tight will cause false positives
        # with inaccurate positioning, e.g. indoors, tunnels etc.
        if self._visited_dist < 0.02 and dist > 0.2:
            self.passed = True


class Narrative:

    """Narration of routing maneuvers."""

    def __init__(self):
        """Initialize a :class:`Narrative` instance."""
        self.dist = []
        self.maneuver = []
        self.time = []
        self.x = []
        self.y = []

    def get_closest_node(self, x, y):
        """Return index of the route node closest to coordinates."""
        min_index = 0
        min_sq_dist = 360**2
        for i in range(len(self.x)):
            # This should be faster than haversine
            # and probably close enough.
            dist = (x - self.x[i])**2 + (y - self.y[i])**2
            if dist < min_sq_dist:
                min_index = i
                min_sq_dist = dist
        return min_index

    def get_display(self, x, y):
        """Return a dictionary of status details to display."""
        if not self.ready: return None
        node = self.get_closest_node(x, y)
        dest_dist = self.dist[node]
        dest_time = self.time[node]
        if node == len(self.dist) - 1:
            # Use exact straight-line value at the very end.
            dest_dist = poor.util.calculate_distance(
                x, y, self.x[node], self.y[node])
        dest_dist = poor.util.format_distance(dest_dist, 2)
        dest_time = poor.util.format_time(dest_time)
        man = self._get_maneuver_display(x, y, node)
        man_dist, man_time, icon, narrative = man
        man_time_float = man_time
        if man_dist is not None:
            man_dist = poor.util.format_distance(man_dist, 2)
            man_time = poor.util.format_time(man_time)
        return dict(dest_dist=dest_dist,
                    dest_time=dest_time,
                    man_dist=man_dist,
                    man_time=man_time,
                    man_time_float=man_time_float,
                    icon=icon,
                    narrative=narrative)

    def _get_maneuver_display(self, x, y, node):
        """Return maneuver details to display."""
        if self.maneuver[node] is None:
            return None, None, None, None
        maneuver = self.maneuver[node]
        man_dist = self.dist[node] - self.dist[maneuver.node]
        man_time = self.time[node] - self.time[maneuver.node]
        if node == maneuver.node:
            # Use exact straight-line value at the very end.
            man_dist = poor.util.calculate_distance(
                x, y, maneuver.x, maneuver.y)
            maneuver.set_visited(man_dist)
            if maneuver.passed and node+1 < len(self.x):
                # If the maneuver point has been passed,
                # show the next maneuver narrative if applicable.
                return self._get_maneuver_display(x, y, node+1)
        return man_dist, man_time, maneuver.icon, maneuver.narrative

    @property
    def ready(self):
        """Return ``True`` if narrative is in steady state and ready for use."""
        return (self.x and
                len(self.x) ==
                len(self.y) ==
                len(self.dist) ==
                len(self.time) ==
                len(self.maneuver))

    def set_maneuvers(self, maneuvers):
        """Set maneuver points and corresponding narrative."""
        prev_maneuver = None
        for i in reversed(range(len(maneuvers))):
            maneuver = Maneuver(**maneuvers[i])
            maneuver.node = self.get_closest_node(maneuver.x, maneuver.y);
            self.maneuver[maneuver.node] = maneuver
            # Assign maneuver to preceding nodes as well.
            for j in reversed(range(maneuver.node)):
                self.maneuver[j] = maneuver
                if self.dist[j] - self.dist[maneuver.node] > 10: break
            # Calculate time remaining to destination for each node
            # based on durations of individual legs following given maneuvers.
            if prev_maneuver is not None:
                dist = self.dist[maneuver.node] - self.dist[prev_maneuver.node]
                speed = dist / max(1, maneuvers[i]["duration"]) # km/s
                for j in reversed(range(maneuver.node, prev_maneuver.node)):
                    dist = self.dist[j] - self.dist[j+1]
                    self.time[j] = self.time[j+1] + dist/speed
            prev_maneuver = maneuver

    def set_route(self, x, y):
        """Set route from coordinates."""
        self.x = x
        self.y = y
        self.dist = [0] * len(x)
        self.time = [0] * len(x)
        self.maneuver = [None] * len(x)
        for i in reversed(range(len(x)-1)):
            dist = poor.util.calculate_distance(x[i], y[i], x[i+1], y[i+1])
            self.dist[i] = self.dist[i+1] + dist
            # Calculate remaining time using 120 km/h, which will maximize
            # the advance at which maneuver notifications are shown.
            # See 'set_maneuvers' for the actual leg-specific times
            # that should in most cases overwrite these.
            self.time[i] = self.time[i+1] + (dist/120)*3600

    def unset(self):
        """Unset route and maneuvers."""
        self.dist = []
        self.maneuver = []
        self.time = []
        self.x = []
        self.y = []