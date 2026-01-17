# Workflow Features: Conditionals and Loops

Complete guide to advanced workflow features including conditional execution and loops.

## Quick Reference

### Conditionals

```yaml
- id: step_name
  step: Operation Name
  if: success()  # Condition expression
```

**Available Functions:**
- `success()` - Run if all previous steps succeeded
- `failure()` - Run if any previous step failed
- `always()` - Always run regardless of outcomes
- `steps.<id>.status` - Check specific step status (`'success'`, `'failure'`, `'skipped'`)
- `steps.<id>.result` - Access step return values

**Operators:** `==`, `!=`, `&&`, `||`, `not`

### Loops

```yaml
- id: step_name
  step: Operation Name
  loop:
    count: 3           # Fixed iterations
    # OR
    items: [1, 2, 3]   # Iterate over list
    # OR
    while: condition   # Conditional looping
```

**Loop Variables:**
- `loop.index` - Current iteration (0-based)
- `loop.item` - Current item (when using items)

## Feature Matrix

| Feature | Syntax | Example |
|---------|--------|---------|
| **Fixed Loop** | `loop: { count: N }` | Retry 3 times |
| **Item Loop** | `loop: { items: [...] }` | Process list of files |
| **While Loop** | `loop: { while: condition }` | Poll until ready |
| **Conditional Step** | `if: expression` | Run only on success |
| **Step Status** | `steps.X.status` | Check if step passed |
| **Step Result** | `steps.X.result` | Access return value |
| **Loop Index** | `loop.index` | Get iteration number |
| **Loop Item** | `loop.item` | Get current item |

## Complete Example

```yaml
name: Advanced Workflow
description: Demonstrates conditionals and loops together

steps:
  # Step 1: Setup
  - id: setup
    step: Initialize Environment
    description: Initial setup

  # Step 2: Retry loop
  - id: fetch_data
    step: Fetch Remote Data
    loop:
      count: 3
      while: steps.fetch_data[loop.index].status == 'failure'
    description: Retry fetch up to 3 times on failure

  # Step 3: Conditional based on loop result
  - id: process_if_fetched
    step: Process Data
    if: steps.fetch_data[0].status == 'success'
    description: Only process if first fetch succeeded

  # Step 4: Item iteration with condition
  - id: deploy_environments
    step: Deploy Application
    if: success()
    loop:
      items:
        - dev
        - staging
        - prod
    arguments:
      environment: ${{ loop.item }}
    description: Deploy to all environments if tests passed

  # Step 5: Conditional cleanup on failure
  - id: rollback
    step: Rollback Changes
    if: failure()
    description: Rollback if anything failed

  # Step 6: Always cleanup
  - id: cleanup
    step: Cleanup Resources
    if: always()
    description: Always cleanup temporary files

  # Step 7: Final report
  - id: report
    step: Generate Report
    if: steps.cleanup.status == 'success' && steps.deploy_environments[2].status == 'success'
    description: Report if cleanup succeeded and production deployed
```

## Integration Examples

### Retry Pattern with Exponential Backoff

```yaml
- id: retry_connection
  step: Connect to Service
  loop:
    count: 5
  description: Retry connection up to 5 times

- id: verify_connection
  step: Verify Connection
  if: steps.retry_connection[4].status != 'success'
  description: Escalate if all retries failed
```

### Batch Processing with Progress Tracking

```yaml
- id: process_batches
  step: Process Batch
  loop:
    count: 10
  arguments:
    batch_id: ${{ loop.index }}
    total_batches: 10

- id: verify_all_batches
  step: Verify Results
  if: success()
  description: Verify only if all batches succeeded
```

### Environment-Specific Deployment

```yaml
- id: run_tests
  step: Run Test Suite

- id: deploy_nonprod
  step: Deploy Application
  if: success()
  loop:
    items: [dev, qa]
  arguments:
    environment: ${{ loop.item }}

- id: manual_approval
  step: Wait for Approval
  if: steps.deploy_nonprod[1].status == 'success'

- id: deploy_prod
  step: Deploy Application
  if: steps.manual_approval.status == 'success'
  arguments:
    environment: prod
```

### State Machine Implementation

```yaml
- id: initialize
  step: Initialize System

- id: state_transitions
  step: Transition State
  if: success()
  loop:
    items:
      - PENDING
      - ACTIVE
      - PROCESSING
      - COMPLETE
  arguments:
    target_state: loop.item

- id: error_state
  step: Transition State
  if: failure()
  arguments:
    target_state: ERROR
```

## Accessing Loop Results

When a step has a loop, each iteration gets a unique ID with bracket notation:

```yaml
- id: my_loop
  step: Some Operation
  loop:
    count: 3

# Results are stored as:
# - steps.my_loop[0] - First iteration
# - steps.my_loop[1] - Second iteration
# - steps.my_loop[2] - Third iteration

- id: check_specific
  step: Another Operation
  if: steps.my_loop[1].status == 'success'
```

## Best Practices

### Conditionals

1. **Be Explicit**: Use descriptive conditions: `steps.validation.status == 'success'` over `success()`
2. **Document Intent**: Add descriptions explaining why conditions exist
3. **Test Both Paths**: Ensure your workflow handles both success and failure scenarios
4. **Use always()**: For cleanup steps to prevent resource leaks
5. **Check Results**: Use `steps.X.result != None` to verify steps returned data

### Loops

1. **Limit Iterations**: Keep loop counts reasonable; while loops max at 100
2. **Early Exit**: Use `loop.while` conditions to stop early when possible
3. **Descriptive IDs**: Clear step IDs help when referencing iterations
4. **Error Handling**: Loops break on error; plan for partial completion
5. **Progress Tracking**: Use `loop.index` in logging/arguments to track progress

### Combined Features

1. **Conditional Loops**: Start loops based on conditions: `if: success()`
2. **Loop Conditions**: Use `loop.while` to exit early based on results
3. **Result Checking**: Reference specific iterations: `steps.loop_id[0].status`
4. **Layered Logic**: Combine `if` and `loop.while` for complex control flow

## Troubleshooting

### Condition Not Working

- Check syntax: Use `==` not `=`, `&&` not `and`
- Verify step IDs match exactly (case-sensitive)
- Ensure referenced steps have executed before condition evaluates

### Loop Not Terminating

- Check `while` condition evaluates to false eventually
- Remember 100 iteration safety limit
- Verify loop variables are updated correctly

### Can't Access Loop Iteration

- Use bracket notation: `steps.step_id[0]` not `steps.step_id.0`
- Ensure you're referencing the right iteration index (0-based)
- Check that the loop has executed before accessing results

## See Also

- [Conditional Execution Guide](conditional_execution.md) - Detailed conditional syntax
- [Loop Examples](../scenarios/loop_examples.yaml) - Working loop examples
- [Conditional Examples](../scenarios/conditional_workflow_demo.yaml) - Working conditional examples
