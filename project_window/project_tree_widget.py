from gettext import gettext as _, pgettext
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QMenu,
                             QMessageBox, QInputDialog, QHeaderView, QAbstractItemView, QToolButton,
                             QApplication)
from PyQt5.QtCore import Qt, QEvent, QSize, QPoint, QRect, QTimer
from PyQt5.QtGui import QIcon, QFont, QBrush, QColor, QPainter, QPen
import project_window.tree_manager as tree_manager
import project_window.project_structure_manager as psm
from settings.theme_manager import ThemeManager


class _DropIndicatorOverlay(QWidget):
    """Transparent overlay that paints the horizontal drop-position indicator line."""

    def __init__(self, parent_viewport):
        super().__init__(parent_viewport)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._line = None  # (y, x_start, x_end)
        self.hide()

    def set_line(self, y=None, x_start=0, x_end=0):
        self._line = (y, x_start, x_end) if y is not None else None
        self.update()

    def paintEvent(self, event):
        if not self._line:
            return
        y, x1, x2 = self._line
        x2 = max(x2, x1 + 30)
        p = QPainter(self)
        try:
            pen = QPen(QColor(0, 120, 215), 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            p.setPen(pen)
            p.drawLine(x1, y, x2, y)
            # Small filled circle at the left end
            p.setBrush(QBrush(QColor(0, 120, 215)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPoint(x1, y), 4, 4)
        finally:
            p.end()


class ProjectTreeWidget(QWidget):
    """Left panel with the project structure tree."""

    # Mapping of English status values to translated display values
    STATUS_MAP = {
        "To Do": pgettext("status", "To Do"),
        "In Progress": pgettext("status", "In Progress"),
        "Final Draft": pgettext("status", "Final Draft")
    }
    
    # Reverse mapping for translating user selections back to English
    REVERSE_STATUS_MAP = {v: k for k, v in STATUS_MAP.items()}
    
    # drag-drop constants
    _DND_THRESHOLD   = 5   # pixels of movement before drag is considered started
    _DND_SCROLL_MARGIN  = 30  # px from edge of viewport that triggers auto-scroll
    _DND_SCROLL_SPEED   = 10  # px per timer tick
    _DND_SCROLL_INTERVAL = 50  # ms

    def __init__(self, controller, model):
        super().__init__()
        self.controller = controller
        self.model = model
        self.tree = QTreeWidget()
        # drag-drop state
        self._dragging        = False
        self._drag_item       = None   # QTreeWidgetItem being dragged
        self._drag_start_pos  = None   # QPoint where LMB was pressed
        self._drag_orig_fg    = [None, None]  # saved foreground brushes [col0, col1]
        self._drop_target     = None   # (parent, insert_index, line_y, line_x)
        self._last_drag_pos   = None   # last cursor pos during drag (for auto-scroll)
        self._overlay         = None   # _DropIndicatorOverlay (created in _init_dnd)
        self._auto_scroll_timer = QTimer(self)
        self._auto_scroll_timer.setInterval(self._DND_SCROLL_INTERVAL)
        self._auto_scroll_timer.timeout.connect(self._dnd_auto_scroll)
        self._auto_scroll_dir = 0

        self.init_ui()
        self.model.structureChanged.connect(self.refresh_tree)
        self.model.errorOccurred.connect(self.show_error_message)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(self.tree)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree.setHeaderLabels([_("Name"), _("Status")])
        self.tree.setColumnCount(2)
        self.tree.setIndentation(5)  # Reduced indentation for left-justified appearance

        header_item = self.tree.headerItem()
        assert header_item is not None
        header_item.setToolTip(1, _("Status"))

        header = self.tree.header()
        assert header is not None
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)

        self.tree.setColumnWidth(1, 40)  # 30 + 10 for scroll bar
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.currentItemChanged.connect(self.controller.tree_item_changed)
        # Disable default double-click expand/collapse so we can use it for renaming.
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        # Listen for Enter/Return key presses on the tree to trigger renaming.
        self.tree.installEventFilter(self)
        self._init_add_hover_button()
        self._init_dnd()
        self.populate()

    def _init_add_hover_button(self):
        """Create the floating '+' button shown on hover over act and chapter rows."""
        # The button is a child of the tree's viewport so it floats above rows.
        viewport = self.tree.viewport()
        assert viewport is not None
        self._add_hover_button = QToolButton(viewport)
        self._add_hover_button.setIcon(
            ThemeManager.get_tinted_icon("assets/icons/plus.svg", QColor("green"))
        )
        self._add_hover_button.setIconSize(QSize(16, 16))
        self._add_hover_button.setFixedSize(QSize(20, 20))
        self._add_hover_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_hover_button.setAutoRaise(True)
        self._add_hover_button.setStyleSheet("QToolButton { border: none; background: transparent; }")
        self._add_hover_button.hide()
        self._hovered_item = None
        self._hovered_item_level = -1
        self._add_hover_button.clicked.connect(self._on_add_hover_button_clicked)

        # Enable mouse tracking and listen for movement / leave on the viewport.
        self.tree.setMouseTracking(True)
        viewport.setMouseTracking(True)
        viewport.installEventFilter(self)

        # Reposition / hide on scroll so the button doesn't drift.
        v_scroll = self.tree.verticalScrollBar()
        assert v_scroll is not None
        h_scroll = self.tree.horizontalScrollBar()
        assert h_scroll is not None
        v_scroll.valueChanged.connect(self._hide_add_hover_button)
        h_scroll.valueChanged.connect(self._hide_add_hover_button)


    def _init_dnd(self):
        """Create the drop-indicator overlay widget."""
        vp = self.tree.viewport()
        self._overlay = _DropIndicatorOverlay(vp)
        self._overlay.resize(vp.size())

    def eventFilter(self, obj, event):
        """unified event filter for tree viewport (hover button + drag-drop)"""
        if obj is self.tree.viewport():
            etype = event.type()

            # keep overlay the same size when viewport is resized
            if etype == QEvent.Type.Resize:
                if self._overlay:
                    self._overlay.resize(event.size())

            # mouse press: record potential drag origin
            elif etype == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton and not self._dragging:
                    item = self.tree.itemAt(event.pos())
                    if item is not None:
                        self._drag_item      = item
                        self._drag_start_pos = QPoint(event.pos())
                # Don't consume; let the tree handle selection.

            # Handle mouse move
            elif etype == QEvent.Type.MouseMove:
                # Check whether drag threshold has been crossed.
                if (self._drag_item is not None
                        and not self._dragging
                        and self._drag_start_pos is not None):
                    delta = event.pos() - self._drag_start_pos
                    if delta.manhattanLength() >= self._DND_THRESHOLD:
                        self._dnd_begin()

                if self._dragging:
                    self._dnd_update(event.pos())
                    return True   # consume to prevent rubber-band selection
                else:
                    self._update_add_hover_button(event.pos())

            # Handle mouse LB release
            elif etype == QEvent.Type.MouseButtonRelease:
                if self._dragging and event.button() == Qt.MouseButton.LeftButton:
                    self._dnd_finish()
                    return True
                else:
                    # Drag never started – just clear the candidate.
                    self._drag_item      = None
                    self._drag_start_pos = None

            # Handle cursor leaving viewport
            elif etype == QEvent.Type.Leave:
                if self._dragging:
                    # Hide indicator and show forbidden cursor until cursor returns.
                    self._drop_target = None
                    self.tree.viewport().setCursor(Qt.CursorShape.ForbiddenCursor)
                    if self._overlay:
                        self._overlay.set_line()
                else:
                    self._hide_add_hover_button()

        # Pressing Enter on the tree triggers renaming.
        elif obj is self.tree and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                item = self.tree.currentItem()
                if item is not None:
                    psm.rename_item(self.controller, item)
                    return True

        return super().eventFilter(obj, event)

    ## drag lifecycle ##

    def _dnd_begin(self):
        """Visually start the drag operation."""
        self._dragging = True
        self._hide_add_hover_button()
        # Dim the item being dragged.
        self._drag_orig_fg[0] = self._drag_item.foreground(0)
        self._drag_orig_fg[1] = self._drag_item.foreground(1)
        dim = QBrush(QColor(150, 150, 150))
        self._drag_item.setForeground(0, dim)
        self._drag_item.setForeground(1, dim)
        # Show forbidden cursor until a valid target is found.
        self.tree.viewport().setCursor(Qt.CursorShape.ForbiddenCursor)
        # Activate the overlay.
        if self._overlay is None:
            self._overlay = _DropIndicatorOverlay(self.tree.viewport())
        self._overlay.resize(self.tree.viewport().size())
        self._overlay.show()
        self._overlay.raise_()

    def _dnd_reset(self):
        """Cancel / clean up all drag state without executing a drop."""
        self._auto_scroll_timer.stop()
        self._auto_scroll_dir = 0
        # Restore the dragged item's appearance.
        if self._dragging and self._drag_item is not None:
            if self._drag_orig_fg[0] is not None:
                self._drag_item.setForeground(0, self._drag_orig_fg[0])
            if self._drag_orig_fg[1] is not None:
                self._drag_item.setForeground(1, self._drag_orig_fg[1])
        self._drag_item      = None
        self._drag_start_pos = None
        self._dragging       = False
        self._drop_target    = None
        self._last_drag_pos  = None
        self._drag_orig_fg   = [None, None]
        self.tree.viewport().unsetCursor()
        if self._overlay:
            self._overlay.set_line()
            self._overlay.hide()

    def _dnd_update(self, pos):
        """Recompute and display the drop indicator for *pos* (viewport coords)."""
        self._last_drag_pos = QPoint(pos)
        target = self._dnd_compute_target(pos)
        self._drop_target = target
        viewport = self.tree.viewport()
        assert viewport is not None
        if target:
            viewport.unsetCursor()
            _, _, ly, lx = target
            self._overlay.set_line(ly, lx, viewport.width())
        else:
            viewport.setCursor(Qt.CursorShape.ForbiddenCursor)
            self._overlay.set_line()
        self._dnd_check_autoscroll(pos)

    def _dnd_finish(self):
        """Execute the drop, move the item in the tree, and persist the change."""
        target    = self._drop_target
        drag_item = self._drag_item
        previous_item = self.tree.currentItem()
        self._dnd_reset()

        if target is None or drag_item is None:
            return

        parent, insert_index, _ly, _lx = target

        # Remove item from current parent
        cur_parent = drag_item.parent()
        if cur_parent is None:
            cur_index = self.tree.indexOfTopLevelItem(drag_item)
            self.tree.takeTopLevelItem(cur_index)
        else:
            cur_index = cur_parent.indexOfChild(drag_item)
            cur_parent.takeChild(cur_index)

        # Adjust index when moving within the same parent
        root = self.tree.invisibleRootItem()
        same_parent = (cur_parent is None and parent is root) or (cur_parent is parent)
        if same_parent and insert_index > cur_index:
            insert_index -= 1

        # Insert at the new location
        if parent is root:
            self.tree.insertTopLevelItem(insert_index, drag_item)
        else:
            parent.insertChild(insert_index, drag_item)

        # Persist and notify
        self.model.update_structure(self.tree)
        hierarchy = self.controller.get_item_hierarchy(drag_item)
        uuid_val  = drag_item.data(0, Qt.ItemDataRole.UserRole)["uuid"]
        self.model.structureChanged.emit(hierarchy, uuid_val)

        # Select only after the model is updated so the editor reload uses the new hierarchy.
        self.tree.setCurrentItem(drag_item)

        # If the dragged item was already selected, currentItemChanged may not fire.
        # Force a reload to keep the editor content in sync with the moved scene.
        if previous_item is drag_item and hasattr(self.controller, "load_current_item_content"):
            self.controller.load_current_item_content()

    ## drop-target computation ##

    def _dnd_row_height(self):
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            r = self.tree.visualItemRect(root.child(i))
            if r.height() > 0:
                return r.height()
        return 24

    def _dnd_last_visible(self, item):
        """Return the last visible descendant of *item* (item itself if collapsed)."""
        if not item.isExpanded() or item.childCount() == 0:
            return item
        return self._dnd_last_visible(item.child(item.childCount() - 1))

    def _dnd_item_at_or_near(self, pos):
        """Return the tree item at *pos*, or the nearest one just above it."""
        item = self.tree.itemAt(pos)
        if item:
            return item
        rh = self._dnd_row_height()
        # Search upward within ~1 row height of empty space.
        for dy in range(1, rh + 4):
            item = self.tree.itemAt(QPoint(pos.x(), pos.y() - dy))
            if item:
                return item
        return None

    def _dnd_is_noop(self, parent, insert_index):
        """Return True when the drop would leave the item in its current position."""
        drag_item   = self._drag_item
        drag_parent = drag_item.parent()
        root        = self.tree.invisibleRootItem()

        # If parents differ it's never a no-op.
        if parent is root:
            if drag_parent is not None:
                return False
            cur_idx = self.tree.indexOfTopLevelItem(drag_item)
        else:
            if drag_parent is not parent:
                return False
            cur_idx = parent.indexOfChild(drag_item)

        return insert_index in (cur_idx, cur_idx + 1)

    def _dnd_compute_target(self, pos):
        """
        Compute (parent_item, insert_index, line_y, line_x) for the cursor
        position *pos*, or None if no valid drop location exists there.
        """
        drag_item = self._drag_item
        if not drag_item:
            return None
        drag_level = self.get_item_level(drag_item)

        item = self._dnd_item_at_or_near(pos)
        if item is None:
            return None

        level      = self.get_item_level(item)
        rect       = self.tree.visualItemRect(item)
        upper_half = pos.y() < rect.center().y()

        # Act (level 0)
        if drag_level == 0:
            if level != 0:
                return None   # chapters / scenes are not valid neighbours for acts
            root = self.tree.invisibleRootItem()
            idx  = self.tree.indexOfTopLevelItem(item)
            if upper_half:
                insert_index = idx
                line_y       = rect.top()
            else:
                insert_index = idx + 1
                last         = self._dnd_last_visible(item)
                line_y       = self.tree.visualItemRect(last).bottom()
            line_x = rect.left()
            parent = root

        # Chapter (level 1)
        elif drag_level == 1:
            if level == 1:
                act_item = item.parent()
                if act_item is None:
                    return None
                parent = act_item
                idx    = act_item.indexOfChild(item)
                if upper_half:
                    insert_index = idx
                    line_y       = rect.top()
                else:
                    insert_index = idx + 1
                    last         = self._dnd_last_visible(item)
                    line_y       = self.tree.visualItemRect(last).bottom()
                line_x = rect.left()

            elif level == 0:
                act_item = item
                if act_item.childCount() == 0:
                    # Empty act: accept the chapter as its only child.
                    parent       = act_item
                    insert_index = 0
                    line_y       = rect.center().y()
                    line_x       = rect.left() + self.tree.indentation()
                elif act_item.isExpanded():
                    # Insert before the first chapter (just below the act header).
                    parent       = act_item
                    insert_index = 0
                    line_y       = rect.bottom()
                    line_x       = self.tree.visualItemRect(act_item.child(0)).left()
                else:
                    return None   # Collapsed non-empty act
            else:
                return None   # Scene level – invalid for chapter drag

        # Scene (level 2)
        elif drag_level == 2:
            if level == 2:
                ch_item = item.parent()
                if ch_item is None:
                    return None
                parent = ch_item
                idx    = ch_item.indexOfChild(item)
                if upper_half:
                    insert_index = idx
                    line_y       = rect.top()
                else:
                    insert_index = idx + 1
                    line_y       = rect.bottom()
                line_x = rect.left()

            elif level == 1:
                ch_item = item
                if ch_item.childCount() == 0:
                    # Empty chapter: accept the scene as its only child.
                    parent       = ch_item
                    insert_index = 0
                    line_y       = rect.center().y()
                    line_x       = rect.left() + self.tree.indentation()
                elif ch_item.isExpanded():
                    # Insert before the first scene.
                    parent       = ch_item
                    insert_index = 0
                    line_y       = rect.bottom()
                    line_x       = self.tree.visualItemRect(ch_item.child(0)).left()
                else:
                    return None   # Collapsed non-empty chapter
            else:
                return None   # Act level – invalid for scene drag

        else:
            return None

        if self._dnd_is_noop(parent, insert_index):
            return None

        return (parent, insert_index, line_y, line_x)

    ## auto-scroll ##

    def _dnd_check_autoscroll(self, pos):
        vp_h = self.tree.viewport().height()
        if pos.y() < self._DND_SCROLL_MARGIN:
            self._auto_scroll_dir = -1
            if not self._auto_scroll_timer.isActive():
                self._auto_scroll_timer.start()
        elif pos.y() > vp_h - self._DND_SCROLL_MARGIN:
            self._auto_scroll_dir = 1
            if not self._auto_scroll_timer.isActive():
                self._auto_scroll_timer.start()
        else:
            self._auto_scroll_dir = 0
            self._auto_scroll_timer.stop()

    def _dnd_auto_scroll(self):
        sb = self.tree.verticalScrollBar()
        sb.setValue(sb.value() + self._auto_scroll_dir * self._DND_SCROLL_SPEED)
        # Re-evaluate drop target after the scroll moves the rows.
        if self._last_drag_pos is not None and self._dragging:
            self._dnd_update(self._last_drag_pos)

    ## Hover button helpers ##

    def _update_add_hover_button(self, pos):
        """Show the '+' button next to the act or chapter row under the cursor."""
        item = self.tree.itemAt(pos)
        if item is None:
            self._hide_add_hover_button()
            return
        level = self.get_item_level(item)
        if level == 0:
            tooltip = _("Add Chapter")
        elif level == 1:
            tooltip = _("Add Scene")
        else:
            self._hide_add_hover_button()
            return

        rect = self.tree.visualItemRect(item)
        if not rect.isValid() or rect.height() <= 0:
            self._hide_add_hover_button()
            return

        btn = self._add_hover_button
        btn.setToolTip(tooltip)
        # Place the button on the right edge of the name column, vertically centered.
        margin = 4
        x = self.tree.columnViewportPosition(0) + self.tree.columnWidth(0) - btn.width() - margin
        # Clamp so the button never overlaps the status column or goes off-screen.
        x = max(rect.left() + margin, x)
        y = rect.top() + (rect.height() - btn.height()) // 2
        btn.move(x, y)
        self._hovered_item = item
        self._hovered_item_level = level
        btn.show()
        btn.raise_()

    def _hide_add_hover_button(self, *_args):
        self._hovered_item = None
        self._hovered_item_level = -1
        if hasattr(self, "_add_hover_button"):
            self._add_hover_button.hide()

    def _on_add_hover_button_clicked(self):
        item = self._hovered_item
        level = self._hovered_item_level
        self._hide_add_hover_button()
        if item is None:
            return
        if level == 0:
            psm.add_chapter(self.controller, item)
        elif level == 1:
            psm.add_scene(self.controller, item)

    def _on_item_double_clicked(self, item, _column):
        """Rename the item on double click (overrides default expand/collapse)."""
        if item is not None:
            psm.rename_item(self.controller, item)

    def populate(self):
        """Populate the tree with the project structure."""
        tree_manager.populate_tree(self.tree, self.model.structure)
        self.assign_all_icons()

    def update_scene_status_icon(self, item):
        """Update the status icon for a scene item."""
        tint = self.controller.icon_tint
        status = item.data(0, Qt.ItemDataRole.UserRole).get("status", "To Do")
        icons = {
            "To Do": "assets/icons/circle.svg",
            "In Progress": "assets/icons/loader.svg",
            "Final Draft": "assets/icons/check-circle.svg"
        }
        item.setIcon(1, ThemeManager.get_tinted_icon(icons.get(status, ""), tint) if status in icons else QIcon())
        item.setText(1, "")

    def get_item_level(self, item):
        """Calculate the level of an item in the tree."""
        level = 0
        temp = item
        while temp.parent():
            level += 1
            temp = temp.parent()
        return level

    def refresh_tree(self, hierarchy, uuid):
        """Refresh the tree structure based on the model's data."""
        self._sync_tree_with_structure(hierarchy, uuid)

    def _sync_tree_with_structure(self, hierarchy, uuid):
        """Synchronize the tree with the project structure incrementally."""
        def find_item_by_uuid(parent, target_uuid, level=0):
            for i in range(parent.childCount()):
                child_item = parent.child(i)
                item_data = child_item.data(0, Qt.ItemDataRole.UserRole)
                if item_data.get("uuid") == target_uuid:
                    return child_item, level
                found, found_level = find_item_by_uuid(child_item, target_uuid, level + 1)
                if found:
                    return found, found_level
            return None, -1

        root = self.tree.invisibleRootItem()
        assert root is not None
        item, level = find_item_by_uuid(root, uuid)
        if item:
            node = self.model._get_node_by_hierarchy(hierarchy)
            if node:
                item.setText(0, node["name"])
                item.setData(0, Qt.ItemDataRole.UserRole, node)
                self.assign_item_icon(item, level)
            else:
                parent = item.parent() or root
                parent.removeChild(item)
        else:
            self.populate()
            new_item = self.find_item_by_hierarchy(hierarchy)
            if new_item:
                self.tree.setCurrentItem(new_item)
                self.tree.scrollToItem(new_item, QAbstractItemView.ScrollHint.PositionAtCenter)

    def find_item_by_hierarchy(self, hierarchy):
        """Find a tree item by its hierarchy path."""
        current = self.tree.invisibleRootItem()
        assert current is not None
        for name in hierarchy:
            found = None
            for i in range(current.childCount()):
                item = current.child(i)
                assert item is not None
                if item.text(0) == name:
                    found = item
                    break
            if not found:
                return None
            current = found
        return current

    def assign_item_icon(self, item, level):
        """Assign an icon to a tree item based on its level and status."""
        tint = self.controller.icon_tint
        scene_data = item.data(0, Qt.ItemDataRole.UserRole) or {"name": item.text(0), "status": "To Do"}
        # Create bold font for category items (Acts and Chapters)
        bold_font = QFont()
        bold_font.setBold(True)

        if level < 2:  # Act or Chapter
            item.setIcon(0, ThemeManager.get_tinted_icon("assets/icons/book.svg", tint))
            item.setText(1, "")  # No status for acts or chapters
            # Apply category styling
            item.setBackground(0, QBrush(ThemeManager.get_category_background_color()))
            item.setFont(0, bold_font)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, "true")  # Mark as category
        else:  # Scene
            item.setIcon(0, ThemeManager.get_tinted_icon("assets/icons/edit.svg", tint))
            status = scene_data.get("status", "To Do")
            icons = {
                "To Do": "assets/icons/circle.svg",
                "In Progress": "assets/icons/loader.svg",
                "Final Draft": "assets/icons/check-circle.svg"
            }
            item.setIcon(1, ThemeManager.get_tinted_icon(icons.get(status, ""), tint) if status in icons else QIcon())
            item.setText(1, "")

    def assign_all_icons(self):
        """Recursively assign icons to all items in the tree."""
        def assign_icons_recursively(item, level=0):
            self.assign_item_icon(item, level)
            for i in range(item.childCount()):
                assign_icons_recursively(item.child(i), level + 1)

        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            assert item is not None
            assign_icons_recursively(item)

    def show_context_menu(self, pos):
        """Display context menu for tree items."""
        item = self.tree.itemAt(pos)
        menu = QMenu()
        hierarchy = self.controller.get_item_hierarchy(item) if item else []
        if not item:
            menu.addAction(_("Add Act"), lambda: self.model.add_act(QInputDialog.getText(self, _("Add Act"), _("Enter act name:"))[0]))
        else:
            menu.addAction(_("Rename"), lambda: psm.rename_item(self.controller, item))
            menu.addAction(_("Delete"), lambda: self.model.delete_node(hierarchy))
            menu.addAction(_("Move Up"), lambda: psm.move_item_up(self.controller, item))
            menu.addAction(_("Move Down"), lambda: psm.move_item_down(self.controller, item))
            level = self.get_item_level(item)
            if level == 0:
                menu.addAction(_("Add Chapter"), lambda: psm.add_chapter(self.controller, item))
            elif level == 1:
                menu.addAction(_("Add Scene"), lambda: psm.add_scene(self.controller, item))
            if level >= 2:
                status_menu = menu.addMenu(_("Set Scene Status"))
                assert status_menu is not None
                for english_status, translated_status in self.STATUS_MAP.items():
                    status_menu.addAction(translated_status, lambda s=english_status: self.controller.set_scene_status(item, s))
        viewport = self.tree.viewport()
        assert viewport is not None
        menu.exec_(viewport.mapToGlobal(pos))

    def show_error_message(self, message):
        """Display an error message to the user."""
        QMessageBox.warning(self, _("Duplicate Name Error"), message)

