# Loop Features

This guide demonstrates how to use loops in workflow steps to repeat operations.

## Loop Types

### Fixed Count Loop

Repeat a step a specific number of times using `loop.count`:

```yaml
- id: retry_operation
  step: Some Action
  loop:
    count: 3
  description: Retry up to 3 times
```

Access the current iteration index with `loop.index` (0-based):
- First iteration: `loop.index = 0`
- Second iteration: `loop.index = 1`
- Third iteration: `loop.index = 2`

### Item Iteration Loop

Iterate over a list of items using `loop.items`:

```yaml
- id: process_states
  step: Update Operation State
  loop:
    items:
      - ACTIVATED
      - CONTINGENT
      - NONCONFORMING
      - ENDED
  arguments:
    state: ACTIVATED  # Can reference loop.item in arguments
```

Access values with:
- `loop.index` - Current iteration number (0, 1, 2, ...)
- `loop.item` - Current item from the list

### While Loop

Continue looping while a condition is true using `loop.while`:

```yaml
- id: wait_for_ready
  step: Check Status
  loop:
    while: loop.index < 10
  description: Check up to 10 times
```

**Safety Limit**: While loops have a maximum of 100 iterations to prevent infinite loops.

### Combined Loop Types

You can combine `count` or `items` with `while` to add early termination:

```yaml
- id: retry_with_limit
  step: Risky Operation
  loop:
    count: 10
    while: steps.previous_step.status != 'success'
  description: Retry up to 10 times or until previous step succeeds
```

## Loop Variables

### `loop.index`

Zero-based iteration counter available in all loop types:

```yaml
- id: batch_process
  step: Process Batch
  loop:
    count: 5
  arguments:
    batch_id: ${{ loop.index }}  # Use ${{ loop.index }} in arguments
    batch_size: 100
```

You can reference `loop.index` in:
- **Arguments**: Use `${{ loop.index }}` - e.g., `value: ${{ loop.index }}`
- **While conditions**: Use bare `loop.index < 5` (no `${{ }}`)
- **If conditions**: Use bare `loop.index` - e.g., `if: loop.index == 0`

### `loop.item`

Current item value when using `loop.items`. **Must be explicitly referenced** using `${{ loop.item }}` syntax in arguments:

```yaml
- id: process_states
  step: Update Operation State
  loop:
    items:
      - ACTIVATED
      - CONTINGENT
      - ENDED
  arguments:
    state: ${{ loop.item }}  # Will be replaced with: ACTIVATED, CONTINGENT, ENDED

- id: process_files
  step: Process Data
  loop:
    items:
      - "data1.json"
      - "data2.json"
      - "data3.json"
  arguments:
    filename: ${{ loop.item }}  # Will be: "data1.json", "data2.json", "data3.json"
```

**Important**: Loop variables in arguments must use `${{ loop.item }}` or `${{ loop.index }}` syntax to distinguish them from literal strings. In conditions (like `if:` or `loop.while:`), use bare `loop.item` without the `${{ }}`.

**Examples:**
```yaml
# In arguments - use ${{ }}
arguments:
  state: ${{ loop.item }}
  index: ${{ loop.index }}
  literal: "loop.item"  # This is a literal string

# In conditions - no ${{ }}
if: loop.index > 0
loop:
  while: loop.index < 10
```

## Loop Result Access

Each loop iteration creates a separate result with an indexed ID:

```yaml
- id: looped_step
  step: Some Action
  loop:
    count: 3

# Later, reference specific iterations:
- id: check_first
  step: Another Action
  if: steps.looped_step[0].status == 'success'
  description: Only if first iteration succeeded

- id: check_second
  step: Another Action
  if: steps.looped_step[1].status == 'success'
  description: Only if second iteration succeeded
```

**Note**: Use bracket notation `steps.step_id[index]` to access specific loop iterations.

## Complete Example

```yaml
name: Loop Demo
description: Comprehensive loop examples

steps:
  # Fixed count loop
  - id: batch_process
    step: Process Batch
    loop:
      count: 5
    description: Process 5 batches

  # Item iteration
  - id: deploy_to_environments
    step: Deploy Application
    loop:
      items:
        - development
        - staging
        - production
    arguments:
      environment: ${{ loop.item }}  # Use ${{ loop.item }} in arguments
    description: Deploy to each environment

  # While loop with safety limit
  - id: poll_status
    step: Check Status
    loop:
      while: loop.index < 20
    description: Poll up to 20 times

  # Combined: items + while condition
  - id: conditional_item_loop
    step: Process Item
    loop:
      items: [1, 2, 3, 4, 5]
      while: steps.previous_check.status == 'success'
    description: Process items until previous check fails

  # Conditional execution after loop
  - id: cleanup
    step: Cleanup Resources
    if: steps.batch_process[0].status == 'success'
    description: Cleanup if first batch succeeded
```

## Common Patterns

### Retry with Exponential Backoff

```yaml
- id: retry_api_call
  step: API Request
  loop:
    count: 5
    while: steps.retry_api_call[loop.index].status == 'failure'
  description: Retry up to 5 times on failure
```

### Process List with Early Exit

```yaml
- id: find_first_match
  step: Check Item
  loop:
    items: ["opt1", "opt2", "opt3"]
    while: steps.find_first_match[loop.index].status != 'success'
  description: Stop at first successful match
```

### Batch Processing

```yaml
- id: process_batch
  step: Process Records
  loop:
    count: 10
  arguments:
    batch_number: ${{ loop.index }}  # Use ${{ }} syntax in arguments
    batch_size: 100
```

### State Machine

```yaml
- id: state_transition
  step: Update State
  loop:
    items:
      - INITIALIZING
      - READY
      - ACTIVE
      - COMPLETE
  arguments:
    new_state: ${{ loop.item }}  # Use ${{ }} syntax in arguments
```

## Tips and Best Practices

1. **Use Descriptive Step IDs**: Loop iterations use `[index]` suffix, so clear IDs help: `steps.retry_connection[0]`

2. **Set Safety Limits**: While loops auto-limit to 100 iterations. Design conditions to terminate naturally.

3. **Access Loop Results**: Reference specific iterations with bracket notation when checking loop outcomes.

4. **Combine with Conditions**: Use `if` to conditionally start loops, and `loop.while` to conditionally continue them.

5. **Monitor Performance**: Large loops can slow execution. Consider if parallel execution (future feature) is better.

6. **Loop Variables in Arguments**: Reference `loop.index` and `loop.item` in step arguments for dynamic values.

7. **Error Handling**: Loop breaks on error by default. Use conditions to implement custom retry logic.
