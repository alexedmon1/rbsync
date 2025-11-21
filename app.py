"""
rbsync - Rodent Brain Sync
A slice correspondence tool for multi-modal rat MRI and atlas alignment.

This tool helps researchers identify which atlas slices correspond to sparse
MRI acquisitions (e.g., DTI with thick slices). It displays MRI and atlas
side-by-side, automatically matches slices based on physical coordinates,
and allows manual adjustment for visual verification.

Supports multiple modalities: DTI, T2, parametric maps (MWF, MTr), etc.
"""

import json
import csv
import numpy as np
import nibabel as nib
import napari
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QTextEdit, QSpinBox, QFileDialog
)
from qtpy.QtCore import Qt


class SliceMatcherApp:
    """Main application for MRI-Atlas slice correspondence matching."""

    def __init__(self):
        """Initialize the application."""
        # Data containers
        self.mri_img: Optional[nib.Nifti1Image] = None
        self.atlas_img: Optional[nib.Nifti1Image] = None

        # Cached arrays and affines
        self.mri_data: Optional[np.ndarray] = None
        self.mri_affine: Optional[np.ndarray] = None
        self.atlas_data: Optional[np.ndarray] = None
        self.atlas_affine: Optional[np.ndarray] = None

        # Slice correspondence mapping: {mri_slice_idx: atlas_slice_idx}
        self.slice_mapping: Dict[int, int] = {}

        # Current state
        self.current_mri_slice_idx: int = 0
        self.mri_slice_axis: int = 2  # Default to axial (SI axis)
        self.atlas_slice_axis: int = 2

        # Napari viewer
        self.viewer = napari.Viewer(title="rbsync - Slice Matcher")

        # Initialize UI
        self._build_ui()

    def _build_ui(self):
        """Build the user interface."""
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # === File loading section ===
        file_section = QHBoxLayout()

        self.load_mri_btn = QPushButton("Load MRI")
        self.load_mri_btn.clicked.connect(self.load_mri)
        file_section.addWidget(self.load_mri_btn)

        self.load_atlas_btn = QPushButton("Load Atlas")
        self.load_atlas_btn.clicked.connect(self.load_atlas)
        file_section.addWidget(self.load_atlas_btn)

        main_layout.addLayout(file_section)

        # === MRI slice navigation ===
        main_layout.addWidget(QLabel("MRI Slice Navigation:"))

        mri_nav_layout = QHBoxLayout()
        mri_nav_layout.addWidget(QLabel("Slice:"))

        self.mri_slider = QSlider(Qt.Horizontal)
        self.mri_slider.setMinimum(0)
        self.mri_slider.setMaximum(0)
        self.mri_slider.setValue(0)
        self.mri_slider.valueChanged.connect(self.on_mri_slice_changed)
        mri_nav_layout.addWidget(self.mri_slider)

        self.mri_slice_label = QLabel("0 / 0")
        mri_nav_layout.addWidget(self.mri_slice_label)

        main_layout.addLayout(mri_nav_layout)

        # === Axis selection ===
        axis_layout = QHBoxLayout()
        axis_layout.addWidget(QLabel("Slice Axis:"))

        self.axis_spin = QSpinBox()
        self.axis_spin.setMinimum(0)
        self.axis_spin.setMaximum(2)
        self.axis_spin.setValue(2)
        self.axis_spin.valueChanged.connect(self.on_axis_changed)
        axis_layout.addWidget(self.axis_spin)

        self.axis_label = QLabel("SI (2)")
        axis_layout.addWidget(self.axis_label)

        main_layout.addLayout(axis_layout)

        # === Current correspondence display ===
        main_layout.addWidget(QLabel("Current Correspondence:"))
        self.correspondence_label = QLabel("MRI slice ? → Atlas slice ?")
        self.correspondence_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; padding: 10px; "
            "background-color: #2a2a2a; border-radius: 5px;"
        )
        main_layout.addWidget(self.correspondence_label)

        # === Manual adjustment controls ===
        adjust_layout = QHBoxLayout()
        adjust_layout.addWidget(QLabel("Atlas Slice Adjustment:"))

        self.atlas_minus_btn = QPushButton("← -1")
        self.atlas_minus_btn.clicked.connect(lambda: self.adjust_atlas_slice(-1))
        adjust_layout.addWidget(self.atlas_minus_btn)

        self.atlas_plus_btn = QPushButton("+1 →")
        self.atlas_plus_btn.clicked.connect(lambda: self.adjust_atlas_slice(1))
        adjust_layout.addWidget(self.atlas_plus_btn)

        self.atlas_minus10_btn = QPushButton("← -10")
        self.atlas_minus10_btn.clicked.connect(lambda: self.adjust_atlas_slice(-10))
        adjust_layout.addWidget(self.atlas_minus10_btn)

        self.atlas_plus10_btn = QPushButton("+10 →")
        self.atlas_plus10_btn.clicked.connect(lambda: self.adjust_atlas_slice(10))
        adjust_layout.addWidget(self.atlas_plus10_btn)

        main_layout.addLayout(adjust_layout)

        # === Auto-match button ===
        auto_match_layout = QHBoxLayout()

        self.auto_match_current_btn = QPushButton("Auto-Match Current Slice")
        self.auto_match_current_btn.clicked.connect(self.auto_match_current)
        auto_match_layout.addWidget(self.auto_match_current_btn)

        self.auto_match_all_btn = QPushButton("Auto-Match All Slices")
        self.auto_match_all_btn.clicked.connect(self.auto_match_all)
        auto_match_layout.addWidget(self.auto_match_all_btn)

        main_layout.addLayout(auto_match_layout)

        # === Export section ===
        export_layout = QHBoxLayout()

        self.export_json_btn = QPushButton("Export Mapping (JSON)")
        self.export_json_btn.clicked.connect(lambda: self.export_mapping('json'))
        export_layout.addWidget(self.export_json_btn)

        self.export_csv_btn = QPushButton("Export Mapping (CSV)")
        self.export_csv_btn.clicked.connect(lambda: self.export_mapping('csv'))
        export_layout.addWidget(self.export_csv_btn)

        main_layout.addLayout(export_layout)

        # === Status log ===
        main_layout.addWidget(QLabel("Status Log:"))
        self.status_log = QTextEdit()
        self.status_log.setReadOnly(True)
        self.status_log.setMaximumHeight(120)
        main_layout.addWidget(self.status_log)

        main_widget.setLayout(main_layout)
        self.viewer.window.add_dock_widget(main_widget, area='right', name='Controls')

        self.log("rbsync initialized. Load MRI and Atlas to begin.")

    def log(self, message: str):
        """Append a message to the status log."""
        self.status_log.append(f"> {message}")
        print(f"[rbsync] {message}")

    def load_mri(self):
        """Load sparse MRI volume (DTI, T2, parametric map, etc.)."""
        file_path, _ = QFileDialog.getOpenFileName(
            None, "Load MRI Volume", "", "NIfTI files (*.nii *.nii.gz)"
        )
        if not file_path:
            return

        try:
            self.mri_img = nib.load(file_path)
            self.mri_data = self.mri_img.get_fdata()
            self.mri_affine = self.mri_img.affine

            # Determine number of slices along current axis
            num_slices = self.mri_data.shape[self.mri_slice_axis]

            self.log(f"Loaded MRI: {Path(file_path).name}")
            self.log(f"  Shape: {self.mri_data.shape}, Axis: {self.mri_slice_axis}, Slices: {num_slices}")

            # Update slider
            self.mri_slider.setMaximum(num_slices - 1)
            self.mri_slider.setValue(0)
            self.mri_slice_label.setText(f"0 / {num_slices - 1}")

            # Initialize mapping
            self.slice_mapping = {}

            # Display first slice
            self.update_display()

        except Exception as e:
            self.log(f"Error loading MRI: {e}")

    def load_atlas(self):
        """Load reference atlas volume."""
        file_path, _ = QFileDialog.getOpenFileName(
            None, "Load Atlas Volume", "", "NIfTI files (*.nii *.nii.gz)"
        )
        if not file_path:
            return

        try:
            self.atlas_img = nib.load(file_path)
            self.atlas_data = self.atlas_img.get_fdata()
            self.atlas_affine = self.atlas_img.affine

            self.log(f"Loaded Atlas: {Path(file_path).name}")
            self.log(f"  Shape: {self.atlas_data.shape}")

            # Display with current MRI slice
            self.update_display()

        except Exception as e:
            self.log(f"Error loading atlas: {e}")

    def on_axis_changed(self, axis: int):
        """Handle axis selection change."""
        axis_names = {0: "AP", 1: "LR", 2: "SI"}
        self.mri_slice_axis = axis
        self.atlas_slice_axis = axis
        self.axis_label.setText(f"{axis_names[axis]} ({axis})")

        if self.mri_data is not None:
            num_slices = self.mri_data.shape[axis]
            self.mri_slider.setMaximum(num_slices - 1)
            self.mri_slider.setValue(0)
            self.mri_slice_label.setText(f"0 / {num_slices - 1}")

            # Reset mapping for new axis
            self.slice_mapping = {}

        self.log(f"Changed axis to: {axis_names[axis]} (axis {axis})")
        self.update_display()

    def on_mri_slice_changed(self, value: int):
        """Handle MRI slice slider change."""
        self.current_mri_slice_idx = value

        if self.mri_data is not None:
            num_slices = self.mri_data.shape[self.mri_slice_axis]
            self.mri_slice_label.setText(f"{value} / {num_slices - 1}")

        self.update_display()

    def get_slice(self, data: np.ndarray, axis: int, idx: int) -> np.ndarray:
        """
        Extract a 2D slice from 3D volume.

        Args:
            data: 3D array
            axis: Slice axis (0, 1, or 2)
            idx: Slice index

        Returns:
            2D slice array
        """
        if axis == 0:
            return data[idx, :, :]
        elif axis == 1:
            return data[:, idx, :]
        else:  # axis == 2
            return data[:, :, idx]

    def get_slice_position_world(self, affine: np.ndarray, axis: int, idx: int) -> float:
        """
        Get the world coordinate position of a slice.

        Args:
            affine: 4x4 affine matrix
            axis: Slice axis
            idx: Slice index

        Returns:
            World coordinate position (mm) along the specified axis
        """
        # Create voxel coordinate
        voxel_coord = np.zeros(4)
        voxel_coord[axis] = idx
        voxel_coord[3] = 1

        # Transform to world coordinates
        world_coord = affine @ voxel_coord

        return world_coord[axis]

    def find_matching_atlas_slice(self, mri_slice_idx: int) -> int:
        """
        Automatically find the atlas slice that best matches the MRI slice
        based on physical world coordinates.

        Args:
            mri_slice_idx: MRI slice index

        Returns:
            Best matching atlas slice index
        """
        if self.mri_affine is None or self.atlas_affine is None or self.atlas_data is None:
            return 0

        # Get world position of MRI slice
        mri_world_pos = self.get_slice_position_world(
            self.mri_affine, self.mri_slice_axis, mri_slice_idx
        )

        # Find closest atlas slice
        num_atlas_slices = self.atlas_data.shape[self.atlas_slice_axis]
        best_atlas_idx = 0
        min_distance = float('inf')

        for atlas_idx in range(num_atlas_slices):
            atlas_world_pos = self.get_slice_position_world(
                self.atlas_affine, self.atlas_slice_axis, atlas_idx
            )
            distance = abs(atlas_world_pos - mri_world_pos)

            if distance < min_distance:
                min_distance = distance
                best_atlas_idx = atlas_idx

        self.log(f"  MRI slice {mri_slice_idx} at {mri_world_pos:.2f}mm → "
                f"Atlas slice {best_atlas_idx} (distance: {min_distance:.2f}mm)")

        return best_atlas_idx

    def auto_match_current(self):
        """Automatically match the current MRI slice to atlas."""
        if self.mri_data is None or self.atlas_data is None:
            self.log("Load both MRI and Atlas first")
            return

        matched_atlas_idx = self.find_matching_atlas_slice(self.current_mri_slice_idx)
        self.slice_mapping[self.current_mri_slice_idx] = matched_atlas_idx

        self.log(f"Auto-matched: MRI {self.current_mri_slice_idx} → Atlas {matched_atlas_idx}")
        self.update_display()

    def auto_match_all(self):
        """Automatically match all MRI slices to atlas."""
        if self.mri_data is None or self.atlas_data is None:
            self.log("Load both MRI and Atlas first")
            return

        num_mri_slices = self.mri_data.shape[self.mri_slice_axis]

        self.log(f"Auto-matching all {num_mri_slices} slices...")
        for mri_idx in range(num_mri_slices):
            matched_atlas_idx = self.find_matching_atlas_slice(mri_idx)
            self.slice_mapping[mri_idx] = matched_atlas_idx

        self.log(f"Auto-matched all slices. Review and adjust as needed.")
        self.update_display()

    def adjust_atlas_slice(self, delta: int):
        """Manually adjust the atlas slice correspondence."""
        if self.current_mri_slice_idx not in self.slice_mapping:
            # Initialize with auto-match if not already mapped
            self.auto_match_current()
            return

        if self.atlas_data is None:
            return

        current_atlas_idx = self.slice_mapping[self.current_mri_slice_idx]
        new_atlas_idx = current_atlas_idx + delta

        # Clamp to valid range
        max_atlas_idx = self.atlas_data.shape[self.atlas_slice_axis] - 1
        new_atlas_idx = max(0, min(new_atlas_idx, max_atlas_idx))

        self.slice_mapping[self.current_mri_slice_idx] = new_atlas_idx
        self.log(f"Adjusted: MRI {self.current_mri_slice_idx} → Atlas {new_atlas_idx}")

        self.update_display()

    def update_display(self):
        """Update the napari display with current MRI and matched atlas slice."""
        if self.mri_data is None:
            return

        # Get MRI slice
        mri_slice = self.get_slice(
            self.mri_data, self.mri_slice_axis, self.current_mri_slice_idx
        )

        # Update or create MRI layer
        if 'MRI' in self.viewer.layers:
            self.viewer.layers['MRI'].data = mri_slice
        else:
            self.viewer.add_image(
                mri_slice,
                name='MRI',
                colormap='gray',
                blending='additive'
            )

        # Get matched atlas slice if available
        if self.atlas_data is not None:
            # Get or auto-compute matching
            if self.current_mri_slice_idx in self.slice_mapping:
                atlas_slice_idx = self.slice_mapping[self.current_mri_slice_idx]
            else:
                atlas_slice_idx = self.find_matching_atlas_slice(self.current_mri_slice_idx)
                # Don't save yet - let user confirm

            atlas_slice = self.get_slice(
                self.atlas_data, self.atlas_slice_axis, atlas_slice_idx
            )

            # Update or create Atlas layer
            if 'Atlas' in self.viewer.layers:
                self.viewer.layers['Atlas'].data = atlas_slice
            else:
                self.viewer.add_image(
                    atlas_slice,
                    name='Atlas',
                    colormap='red',
                    blending='additive',
                    opacity=0.5
                )

            # Update correspondence label
            matched_str = "✓" if self.current_mri_slice_idx in self.slice_mapping else "?"
            self.correspondence_label.setText(
                f"MRI slice {self.current_mri_slice_idx} → Atlas slice {atlas_slice_idx} {matched_str}"
            )
        else:
            self.correspondence_label.setText(
                f"MRI slice {self.current_mri_slice_idx} → Atlas: not loaded"
            )

        # Auto-reset view
        self.viewer.reset_view()

    def export_mapping(self, format_type: str):
        """
        Export the slice correspondence mapping.

        Args:
            format_type: 'json' or 'csv'
        """
        if not self.slice_mapping:
            self.log("No mapping to export. Match slices first.")
            return

        # Get save path
        if format_type == 'json':
            file_path, _ = QFileDialog.getSaveFileName(
                None, "Export Mapping", "slice_mapping.json", "JSON files (*.json)"
            )
        else:
            file_path, _ = QFileDialog.getSaveFileName(
                None, "Export Mapping", "slice_mapping.csv", "CSV files (*.csv)"
            )

        if not file_path:
            return

        try:
            if format_type == 'json':
                # Create metadata
                mapping_data = {
                    'axis': self.mri_slice_axis,
                    'axis_name': {0: 'AP', 1: 'LR', 2: 'SI'}[self.mri_slice_axis],
                    'mri_shape': list(self.mri_data.shape) if self.mri_data is not None else None,
                    'atlas_shape': list(self.atlas_data.shape) if self.atlas_data is not None else None,
                    'mapping': {int(k): int(v) for k, v in self.slice_mapping.items()}
                }

                with open(file_path, 'w') as f:
                    json.dump(mapping_data, f, indent=2)

            else:  # CSV
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['MRI_Slice_Index', 'Atlas_Slice_Index'])
                    for mri_idx in sorted(self.slice_mapping.keys()):
                        writer.writerow([mri_idx, self.slice_mapping[mri_idx]])

            self.log(f"Exported mapping to: {Path(file_path).name}")
            self.log(f"  Total correspondences: {len(self.slice_mapping)}")

        except Exception as e:
            self.log(f"Error exporting mapping: {e}")

    def run(self):
        """Start the napari event loop."""
        napari.run()


def main():
    """Entry point for rbsync application."""
    app = SliceMatcherApp()
    app.run()


if __name__ == '__main__':
    main()
