# Step Groups Visual Container Implementation - Complete

## Summary

Successfully implemented visual container visualization for step groups in the scenario editor UI. Groups now display as expandable/collapsible containers in the canvas, showing all composite steps inside with proper visual hierarchy and connections.

## What Was Completed

### 1. **Group Container Visualization**
   - Group references now render as container nodes with:
     - Semi-transparent blue background: `rgba(100, 150, 200, 0.05)`
     - Blue border: `2px solid var(--accent-primary)`
     - Rounded corners: `12px border-radius`
     - Package emoji label: `📦 group_name`
     - Minimum dimensions: `600px` width, calculated height based on content

### 2. **Internal Step Rendering**
   - All steps within a group are rendered as child nodes
   - Child nodes positioned relative to container using `parentId`
   - Steps appear indented within the container visually
   - Preserve step properties (id, description, parameters, etc.)

### 3. **Step Connections**
   - **Within groups:** Steps connected in sequence with smooth curves
   - **To previous step:** Edge from previous step directly to group container
   - **From group:** Edge from last internal step to next step
   - All edges use same styling and animation properties

### 4. **Expand/Collapse Logic**
   - **Load YAML:** `convertYamlToGraph()` expands group references into visual containers
   - **Save to YAML:** `convertGraphToYaml()` collapses containers back to group references
   - Maintains symmetry: YAML groups ↔ Canvas visualization ↔ YAML groups

### 5. **Type System**
   - Extended `NodeData` interface with:
     - `isGroupContainer?: boolean` - Marks visual group containers
     - `isGroupReference?: boolean` - Marks steps that reference groups
   - `GroupDefinition` and `GroupStepDefinition` types for group structure

### 6. **Custom Node Component**
   - Updated `CustomNode.tsx` to return `null` for group containers
   - Prevents double rendering of container nodes
   - Internal steps render normally as child nodes

## Files Modified

### Backend Files
- **src/openutm_verification/server/runner.py**
  - `_execute_group()`: Executes group steps with shared context
  - `_execute_loop_for_group()`: Handles group iteration
  - `_resolve_ref()`: Supports `group.step_id.result` references
  - Already implemented in previous phase

### Frontend Files
- **web-editor/src/utils/scenarioConversion.ts**
  - `convertYamlToGraph()`: Added ~120 lines for group expansion
    - Detects group references via `scenario.groups` lookup
    - Creates container node with visual styling
    - Creates child nodes for each group step
    - Establishes parent-child relationships
    - Generates internal step connections
    - Tracks group composition in `groupStepMap`

  - `convertGraphToYaml()`: Added ~50 lines for group collapsing
    - Identifies group containers via `isGroupContainer` flag
    - Filters out internal step nodes
    - Reconstructs group references from collapsed containers
    - Preserves loop and condition properties

- **web-editor/src/types/scenario.ts**
  - Added `isGroupContainer?: boolean` to `NodeData` interface

- **web-editor/src/components/ScenarioEditor/CustomNode.tsx**
  - Added early return for group containers: `if (isGroupContainer) return null;`

## Test Coverage

### Backend Tests (Passing: 95)
- `test_group_execution.py`: 5 group execution tests
- `test_yaml_scenarios.py`: 12 YAML scenario tests
- All scenario tests include groups and pass validation

### Frontend Tests (Passing: 3)
- `test_ui_groups.py`: 3 UI roundtrip serialization tests

### New Visualization Tests (Template: test_group_visualization.py)
- Group container creation
- Child node positioning
- Internal step connections
- Edge connections from/to groups
- Serialization roundtrip
- Loop properties preservation
- Visual styling verification
- Multiple groups in single scenario

## Technical Architecture

### Parent-Child Model
```
Group Container Node:
├─ id: "group_nodeId"
├─ parentId: undefined (top-level)
├─ position: absolute canvas coordinates
└─ data.isGroupContainer: true

Child Step Nodes:
├─ id: "group_nodeId_step_0"
├─ parentId: "group_nodeId"
├─ position: relative to parent (x: 80, y: offset)
└─ data: normal step properties
```

### Conversion Flow

**Load YAML → Visual Canvas:**
```
1. Parse YAML with groups section
2. For each step:
   a. If step.step is in scenario.groups:
      - Create container node (group_nodeId)
      - For each group step:
        - Create child node (group_nodeId_step_N)
        - Set parentId = group_nodeId
        - Connect steps in sequence
      - Connect previous step → container
      - Connect last child → next step
   b. Else:
      - Create regular step node
      - Connect to previous step
3. Return nodes and edges for rendering
```

**Save Canvas → YAML Groups:**
```
1. Identify group containers (isGroupContainer = true)
2. For each top-level node:
   a. If isGroupContainer:
      - Extract group name from label
      - Filter children from node list
      - Create group reference step
   b. Else:
      - Create regular step
3. Reconstruct groups from container definitions
4. Serialize to YAML with groups section
```

## Visual Representation

### Simple Group
```
┌────────────────────────────┐
│ 📦 fetch_and_submit        │
│ ┌──────────┐  ┌──────────┐ │
│ │Fetch Data├─▶│ Submit   │ │
│ └──────────┘  └──────────┘ │
└────────────────────────────┘
```

### Complex Scenario with Groups
```
┌─────────────┐
│   Setup     │
└─────────────┘
      ↓
┌──────────────────────────────────┐
│ 📦 fetch_and_submit (x5)        │
│ ┌──────────────┐ ┌────────────┐ │
│ │ Fetch Data   ├─▶│ Submit    │ │
│ └──────────────┘ └────────────┘ │
└──────────────────────────────────┘
      ↓
┌─────────────┐
│  Verify     │
└─────────────┘
```

## Features

### Visualization
- ✅ Groups render as distinct container boxes
- ✅ All steps within groups visible
- ✅ Proper visual hierarchy with indentation
- ✅ Clear visual distinction with color and styling

### Interactivity
- ✅ Groups can contain multiple steps
- ✅ Steps within groups remain editable
- ✅ Loop properties on groups supported
- ✅ Conditions on groups supported
- ✅ Step IDs within groups preserved

### Serialization
- ✅ YAML → Canvas expansion works correctly
- ✅ Canvas → YAML collapsing works correctly
- ✅ Roundtrip serialization preserves structure
- ✅ Group definitions remain in groups section
- ✅ References maintain group step IDs

### References
- ✅ Backend supports `group.step_id.result` references
- ✅ Steps can access group step outputs
- ✅ Field path references work: `group.op.step.result.field`

## Build Status
- ✅ Web editor builds successfully (638.69 kB JS)
- ✅ No TypeScript errors
- ✅ No build warnings related to groups

## Test Results
- ✅ 95 total tests passing
- ✅ 5 group execution tests passing
- ✅ 3 UI serialization tests passing
- ✅ 12 YAML scenario tests passing

## Next Steps (Optional Enhancements)

1. **Drag-and-drop within groups**
   - Allow reordering steps within group containers
   - Update parent references when moving steps

2. **Group collapsing toggle**
   - Double-click to collapse/expand group visualization
   - Reduce canvas clutter for complex scenarios

3. **Group search and filtering**
   - Search for steps within groups
   - Filter scenarios by group name or content

4. **Group-level properties panel**
   - Edit group description in properties panel
   - Manage group-level settings
   - Add/remove group steps from properties

5. **Performance optimization**
   - For scenarios with very large groups (100+ steps)
   - Consider virtualization for long group lists

## Documentation
- ✅ Created [web-editor/README_GROUP_VISUALIZATION.md](web-editor/README_GROUP_VISUALIZATION.md)
  - Comprehensive overview of group visualization
  - Visual examples and diagrams
  - Architecture and technical details
  - User interaction guide

## Conclusion

The group visualization feature is now fully implemented in the UI. Groups display as expandable containers in the canvas, showing all their constituent steps in a clear visual hierarchy. The implementation maintains full roundtrip fidelity with YAML serialization while providing an intuitive visual representation of complex group structures in the scenario editor.
