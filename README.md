# rbsync - Rodent Brain Sync

A slice correspondence tool for multi-modal rat MRI and atlas alignment. This tool helps researchers identify which atlas slices correspond to sparse MRI acquisitions (e.g., DTI with thick slices, limited coverage scans).

## Purpose

When working with multi-modal rodent brain imaging, you often have:
- **Sparse MRI scans**: DTI with 11 slices at 100μm spacing, limited field-of-view T2, etc.
- **Full atlas volumes**: Complete reference brain with dense slice coverage

**rbsync** helps you determine which atlas slices correspond to each MRI slice, enabling downstream analysis and comparison across modalities.

## Features

- **Automatic slice matching** based on physical world coordinates (affine matrices)
- **Visual verification** with side-by-side MRI and atlas display
- **Manual adjustment** with +/- buttons to fine-tune correspondence
- **Multi-modal support**: DTI, T2, parametric maps (MWF, MTr), etc.
- **Export mappings** to JSON or CSV for your analysis pipeline
- **Axis flexibility**: Work with AP, LR, or SI slice orientations

## Requirements

- Python 3.8+
- napari for visualization
- nibabel for NIfTI handling
- See `requirements.txt` for complete list

## Installation

```bash
cd rbsync

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Quick Start

```bash
python app.py
```

### Workflow

1. **Load MRI**: Click "Load MRI" and select your sparse MRI scan (NIfTI format)
   - Examples: DTI volume with 11 slices, limited T2 scan, parametric map

2. **Load Atlas**: Click "Load Atlas" and select your reference atlas volume

3. **Navigate MRI slices**: Use the slice slider to browse through your MRI slices (0 to N-1)

4. **Auto-match slices**:
   - **Current slice**: Click "Auto-Match Current Slice" to match just the visible slice
   - **All slices**: Click "Auto-Match All Slices" to automatically match all MRI slices
   - The tool uses affine matrices to find the atlas slice closest in physical space

5. **Verify and adjust**:
   - Review the side-by-side display (MRI in gray, Atlas in red overlay)
   - If auto-match is incorrect, use adjustment buttons:
     - `← -1` / `+1 →`: Fine adjustment (±1 slice)
     - `← -10` / `+10 →`: Coarse adjustment (±10 slices)
   - A checkmark (✓) indicates confirmed matches, (?) indicates auto-computed but not saved

6. **Export mapping**:
   - Click "Export Mapping (JSON)" for structured metadata + mapping
   - Click "Export Mapping (CSV)" for simple two-column format
   - Use these files in your neurofaune pipeline

### Display

- **Left/Bottom layer**: MRI slice (grayscale, additive blending)
- **Right/Top layer**: Matched atlas slice (red, semi-transparent overlay)
- **Correspondence label**: Shows current mapping (e.g., "MRI slice 5 → Atlas slice 47 ✓")
- **Status log**: Shows all operations, auto-match distances, and export confirmation

## Output Formats

### JSON Export
```json
{
  "axis": 2,
  "axis_name": "SI",
  "mri_shape": [64, 64, 11],
  "atlas_shape": [512, 512, 512],
  "mapping": {
    "0": 150,
    "1": 165,
    "2": 180,
    ...
  }
}
```

### CSV Export
```csv
MRI_Slice_Index,Atlas_Slice_Index
0,150
1,165
2,180
...
```

## How Auto-Matching Works

1. For each MRI slice, the tool:
   - Converts the voxel index to world coordinates (mm) using the MRI affine
   - Searches all atlas slices and converts each to world coordinates using atlas affine
   - Finds the atlas slice with minimum distance in physical space
   - Reports the distance in the status log

2. This works regardless of:
   - Different voxel sizes (MRI vs. atlas)
   - Different image dimensions
   - Different contrast mechanisms (DTI vs. structural)

3. The affine matrices encode:
   - Voxel spacing (resolution)
   - Origin/offset
   - Orientation

## Use Cases

### DTI with 11 Thick Slices
```
MRI: 128×128×11 volume, 0.2mm × 0.2mm × 1.0mm voxels
Atlas: 512×512×512 volume, 0.05mm isotropic
→ rbsync finds the 11 atlas slices that best match your DTI coverage
```

### Parametric Maps (MWF, MTr)
```
MRI: Myelin water fraction map, limited slices due to long acquisition
Atlas: Full anatomical reference
→ rbsync maps your parametric slices to atlas for ROI analysis
```

### Multi-modal Comparison
```
Session 1: DTI → 11 atlas slices
Session 2: T2 → 15 atlas slices
→ Compare which anatomical regions are covered in each modality
```

## Key Functions

- **app.py:285-305** - `get_slice_position_world()`: Convert voxel indices to physical coordinates
- **app.py:307-344** - `find_matching_atlas_slice()`: Automatic correspondence based on affines
- **app.py:346-372** - Auto-matching (current or all slices)
- **app.py:374-394** - Manual adjustment with bounds checking
- **app.py:455-504** - Export to JSON/CSV

## Tips

1. **Check the status log**: Auto-match reports physical distances - large distances may indicate misalignment
2. **Use axis selection**: Ensure you're slicing along the correct anatomical axis (default: SI/axial)
3. **Visual verification is key**: Even with perfect affines, different contrasts may need manual adjustment
4. **Export early, export often**: Save your mapping before closing the app

## Troubleshooting

### Auto-match seems wrong
- Verify your NIfTI files have correct affine matrices (check headers with nibabel)
- Try different slice axes (AP vs. LR vs. SI)
- Use manual adjustment - sometimes contrast differences make visual matching better than geometric

### Display looks stretched/distorted
- This is normal - napari displays in pixel space, not physical space
- The important thing is the slice correspondence, not the visual aspect ratio

### Missing slices in mapping
- Only slices you explicitly auto-match or adjust are saved to the mapping
- Browse through all slices and click "Auto-Match All Slices" to ensure complete coverage

## Integration with neurofaune

The exported JSON/CSV files can be used in your neurofaune pipeline to:
- Extract matching atlas slices for registration targets
- Generate ROI masks in MRI space based on atlas labels
- Compare multi-modal coverage across scanning sessions
- Validate that anatomical regions of interest are captured

## Future Enhancements

- Intensity-based matching (cross-correlation) as alternative to geometric matching
- Batch processing multiple scans
- Direct integration with neurofaune registration pipeline
- 3D visualization of slice positions in volume context
- Support for oblique slice orientations

## Contributing

Part of the neurofaune project. For questions or issues, contact the development team.

## License

To be aligned with neurofaune project licensing.
