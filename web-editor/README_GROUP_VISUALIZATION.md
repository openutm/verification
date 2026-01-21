# Group Visualization in Scenario Editor

## Overview

The scenario editor provides visual representation of step groups as container boxes in the canvas. When a step references a group, all steps within that group are displayed in an expanded view, making it easy to see the composition of the group at a glance.

## Visual Representation

### Group Container

When a scenario includes group references, groups are rendered as:

- **Container nodes** with a distinctive visual style:
  - Semi-transparent blue background (`rgba(100, 150, 200, 0.05)`)
  - Blue border (`2px solid`)
  - Border radius of `12px` for rounded corners
  - Padding of `20px` for internal spacing
  - Minimum width of `600px` and height calculated based on content

### Group Label

Group containers display a label with:
- Package emoji (`📦`) prefix to visually distinguish groups
- Group name (e.g., `📦 fetch_and_submit`)

### Internal Steps

Steps within a group are:
- Rendered as child nodes inside the container
- Positioned relative to the container parent
- Connected in sequence internally
- Included in the visual flow of the scenario

## Architecture

### Data Model

```typescript
// Extended NodeData includes group indicators
interface NodeData {
    isGroupContainer?: boolean;      // Marks this node as a group container
    isGroupReference?: boolean;       // Marks this step as referencing a group
    // ... other properties
}

// Group definition in scenario
interface GroupDefinition {
    description?: string;
    steps: GroupStepDefinition[];
}

interface GroupStepDefinition {
    id?: string;
    step: string;
    arguments?: Record<string, unknown>;
    // ... other step properties
}
```

### Expansion/Collapsing

**Load YAML → Expand in Canvas:**
1. `convertYamlToGraph()` detects group references
2. Creates container node for the group
3. Creates child nodes for each step in the group
4. Establishes parent-child relationships using `parentId`
5. Positions child steps relative to parent container

**Save Canvas → Collapse to YAML:**
1. `convertGraphToYaml()` identifies group containers
2. Filters out internal step nodes
3. Reconstructs group references with extracted group name
4. Saves back to YAML with `groups` section

## User Interactions

### Viewing Groups

1. Load or import a scenario with groups
2. Groups automatically expand in the canvas
3. All steps within groups are visible and editable

### Editing Groups

1. Edit group definitions in the **Groups Manager** panel
2. Add, remove, or modify steps within groups
3. Changes are reflected in the visual canvas
4. On save, canvas collapses back to group references in YAML

### Creating New Groups

1. Open the **Groups Manager** panel
2. Click "Add Group"
3. Enter group name and description
4. Add steps to the group
5. Steps automatically appear as children in the canvas

### Modifying Step Connections

- Steps within groups maintain internal connections
- Group containers connect to:
  - Previous step (edge points from previous step to group container)
  - Next step (edge points from last group step to next step)

## Technical Details

### Parent-Child Relationships

Groups use xyflow's parent-child node relationships:
- Container node: `parentId` is `undefined` (top-level)
- Internal steps: `parentId` equals container node ID
- Relative positioning: Child positions are relative to parent

### Visual Styling

Group containers use inline styles:
```typescript
{
    background: 'rgba(100, 150, 200, 0.05)',
    border: '2px solid var(--accent-primary)',
    borderRadius: '12px',
    padding: '20px',
    minWidth: '600px',
    minHeight: 'calculated'
}
```

### Edge Routing

1. **Incoming edges:** Point to group container ID
2. **Internal edges:** Connect steps in sequence within group
3. **Outgoing edges:** Point from last internal step to next step

## Example

### YAML with Groups

```yaml
name: Example with Groups
description: Shows group visualization

groups:
  fetch_and_submit:
    description: Fetch data and submit
    steps:
      - id: fetch
        step: Fetch Data
        arguments:
          url: "http://api.example.com/data"
      - id: submit
        step: Submit Data
        arguments:
          endpoint: "http://api.example.com/submit"

steps:
  - step: Setup
    arguments:
      delay: 1000
  - step: fetch_and_submit
    id: group_ref_1
    loop:
      iterations: 5
  - step: Verify
    arguments:
      expected: "success"
```

### Canvas Visualization

In the editor canvas:
```
┌─────────────┐
│   Setup     │
└─────────────┘
      ↓
┌──────────────────────────────┐
│ 📦 fetch_and_submit (x5)     │
│ ┌──────────┐    ┌──────────┐ │
│ │Fetch Data├───▶│Submit Dat│ │
│ └──────────┘    └──────────┘ │
└──────────────────────────────┘
      ↓
┌─────────────┐
│   Verify    │
└─────────────┘
```

## Benefits

1. **Clearer Structure:** See the composition of groups at a glance
2. **Reduced Repetition:** Group definitions are reusable and visible
3. **Better Maintainability:** Changes to group content automatically update all references
4. **Visual Feedback:** Understand complex scenarios by grouping related steps
5. **Intuitive Editing:** Edit groups and see the canvas update in real-time

## Reference Resolution

Groups support reference resolution for step outputs:

```yaml
steps:
  - step: fetch_and_submit
    id: group_op
  - step: Process Results
    arguments:
      data: ${{ group.group_op.fetch.result.data }}
```

This allows steps outside a group to access results from specific steps within the group.
