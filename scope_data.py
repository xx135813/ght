#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2021 Timothée Lecomte

# This file is part of Friture.
#
# Friture is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as published by
# the Free Software Foundation.
#
# Friture is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Friture.  If not, see <http://www.gnu.org/licenses/>.

from PyQt5 import QtCore
from PyQt5.QtCore import pyqtProperty
from PyQt5.QtQml import QQmlListProperty # type: ignore

from friture.axis import Axis
from friture.curve import Curve
from friture.triggers import TriggersModel, Trigger
import logging
logger = logging.getLogger(__name__)

class Scope_Data(QtCore.QObject):
    @QtCore.pyqtSlot(int, int, int, int, result=str)
    def update_trigger_params(self, id_, hz, time_ms, vol):
        """UI calls this on OK. Returns empty string on success, else error text."""
        try:
            id_ = int(id_); hz = int(hz); time_ms = int(time_ms); vol = int(vol)
            logger.debug(f"update_trigger_params id_={id_}, hz={hz}, time_ms={time_ms}, vol={vol}")
        except Exception:
            return "internal"
        # Try backend validation/update
        try:
            if hasattr(self._triggers_model, 'validate_and_update'):
                res = self._triggers_model.validate_and_update(id_, hz, time_ms, vol)
                if isinstance(res, str):
                    if res == "":
                        return ""
                    if res != "internal":
                        return res
        except Exception:
            pass
        # Fallback: direct safe update on the Trigger object
        HZ_MIN, HZ_MAX, HZ_STEP = 20, 15000, 10
        T_MIN,  T_MAX,  T_STEP  = 20, 5000,  10
        VOL_MIN, VOL_MAX, VOL_STEP = 0, 100, 1
        def bad(v, lo, hi, step): return not (isinstance(v, int) and lo <= v <= hi and (v - lo) % step == 0)
        if bad(hz, HZ_MIN, HZ_MAX, HZ_STEP):     return f"Hz вне диапазона/шага ({HZ_MIN}…{HZ_MAX}, шаг {HZ_STEP})"
        if bad(time_ms, T_MIN, T_MAX, T_STEP):   return f"time вне диапазона/шага ({T_MIN}…{T_MAX} мс, шаг {T_STEP})"
        if bad(vol, VOL_MIN, VOL_MAX, VOL_STEP): return f"vol вне диапазона/шага ({VOL_MIN}…{VOL_MAX} %, шаг {VOL_STEP})"
        trg = None
        for x in getattr(self._triggers_model, '_triggers', []):
            if getattr(x, 'id', None) == id_:
                trg = x; break
        if trg is None:
            return "internal"
        try:
            setattr(trg, 'Hz', hz)
            setattr(trg, 'time', time_ms)
            setattr(trg, 'vol', vol)
            if hasattr(self._triggers_model, 'model_changed'):
                try: self._triggers_model.model_changed.emit()
                except Exception: pass
            try:
                self._triggers_model.play_test_tone(hz, time_ms, vol)
            except Exception:
                pass
            return ""
        except Exception:
            return "internal"

    show_color_axis_changed = QtCore.pyqtSignal(bool)
    show_legend_changed = QtCore.pyqtSignal(bool)
    plot_items_changed = QtCore.pyqtSignal()
    axis_rev_changed = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._plot_items = []
        self._horizontal_axis = Axis(self)
        self._vertical_axis = Axis(self)
        self._color_axis = Axis(self)
        self._show_color_axis = False
        self._show_legend = True

        # Axis revision counter to trigger QML bindings on Y-range changes
        self._axis_rev = 0
        try:
            self._vertical_axis.scale_division.logical_major_ticks_changed.connect(self._inc_axis_rev)
            self._vertical_axis.scale_division.logical_minor_ticks_changed.connect(self._inc_axis_rev)
        except Exception:
            pass

        # Triggers model for long-levels overlay
        self._triggers_model = TriggersModel(self)
        self._triggers_model.model_changed.connect(self.triggers_changed)

    @pyqtProperty(QQmlListProperty, notify=plot_items_changed) # type: ignore
    def plot_items(self):
        return QQmlListProperty(Curve, self, self._plot_items)

    def insert_plot_item(self, index, plot_item):
        self._plot_items.insert(index, plot_item)
        self.plot_items_changed.emit()

    def add_plot_item(self, plot_item):
        self._plot_items.append(plot_item)
        plot_item.setParent(self) # take ownership
        self.plot_items_changed.emit()

    def remove_plot_item(self, plot_item):
        self._plot_items.remove(plot_item)
        self.plot_items_changed.emit()

    
    @QtCore.pyqtSlot()
    def _inc_axis_rev(self):
        self._axis_rev += 1
        self.axis_rev_changed.emit(self._axis_rev)

    @pyqtProperty(int, notify=axis_rev_changed)  # type: ignore
    def axis_rev(self):
        return int(self._axis_rev)
# ---- Triggers (Stage 1) ----
    triggers_changed = QtCore.pyqtSignal()

    @pyqtProperty(QQmlListProperty, notify=triggers_changed)  # type: ignore
    def triggers(self):
        # Re-expose the model as a list for QML Repeaters
        return QQmlListProperty(Trigger, self, self._triggers_model._triggers)

    @QtCore.pyqtSlot(float)
    def add_trigger(self, level):
        """Create trigger at given data level; set trigger_bool snapshot per current curve level."""
        # Add trigger to model
        self._triggers_model.add_trigger(level)
        # set trigger_bool snapshot based on current displayed level if available
        current = None
        if self._plot_items:
            # Use first curve by default
            try:
                curve = self._plot_items[0]
                y = curve.y_array()
                if y is not None and len(y) > 0:
                    current = float(y[-1])
            except Exception:
                current = None
        # apply snapshot rule
        try:
            t = self._triggers_model._triggers[-1]
            if current is not None:
                t.trigger_bool = (current >= float(level))
            else:
                t.trigger_bool = False
        except Exception:
            pass
        # Update timestamp
        try:
            t.level_ts = int(QtCore.QDateTime.currentSecsSinceEpoch())
        except Exception:
            import time as _time
            t.level_ts = int(_time.time())
        # Notify QML list change
        self.triggers_changed.emit()

    @QtCore.pyqtSlot(float, result=float)
    def toLevel(self, yFrac):
        """yFrac is 0..1 measured from top; returns axis data value."""
        ct = self.vertical_axis.coordinate_transform
        return float(ct.toPlot(1.0 - float(yFrac)))

    @QtCore.pyqtSlot(float, result=float)
    def toNormalizedY(self, level):
        """Return f in [0,1] (from bottom to top inverted in QML later) such that toPlot(f) ~= level."""
        ct = self.vertical_axis.coordinate_transform
        lo, hi = 0.0, 1.0
        target = float(level)
        # Bisection
        for _ in range(32):
            mid = 0.5 * (lo + hi)
            val = float(ct.toPlot(mid))
            if val < target:
                lo = mid
            else:
                hi = mid
        return lo

    @pyqtProperty(Axis, constant=True) # type: ignore
    def horizontal_axis(self):
        return self._horizontal_axis

    @pyqtProperty(Axis, constant=True) # type: ignore
    def vertical_axis(self):
        return self._vertical_axis

    @pyqtProperty(Axis, constant=True)
    def color_axis(self):
        return self._color_axis
    
    @pyqtProperty(bool, notify=show_color_axis_changed)
    def show_color_axis(self):
        return self._show_color_axis
    
    @show_color_axis.setter
    def show_color_axis(self, show_color_axis):
        if self._show_color_axis != show_color_axis:
            self._show_color_axis = show_color_axis
            self.show_color_axis_changed.emit(show_color_axis)
    
    @pyqtProperty(bool, notify=show_legend_changed) # type: ignore
    def show_legend(self):
        return self._show_legend

    @show_legend.setter # type: ignore
    def show_legend(self, show_legend):
        if self._show_legend != show_legend:
            self._show_legend = show_legend
            self.show_legend_changed.emit(show_legend)
