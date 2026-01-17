# Conditional Workflow Execution

This guide demonstrates how to use conditional expressions in workflow steps, similar to GitHub Actions.

## Syntax Overview

Add an `if` condition to any step to control whether it executes based on previous step results:

```yaml
steps:
  - id: step1
    step: Some Action
    if: success()  # Only runs if previous steps succeeded
```

## Available Condition Functions

### `success()`
Returns `true` if all previous steps completed successfully (none failed).

```yaml
- id: deploy
  step: Deploy Application
  if: success()
  description: Only deploy if all tests passed
```

### `failure()`
Returns `true` if any previous step failed.

```yaml
- id: send_alert
  step: Send Notification
  if: failure()
  description: Alert team if any step failed
```

### `always()`
Always returns `true`, ensuring the step runs regardless of previous step outcomes.

```yaml
- id: cleanup
  step: Teardown Resources
  if: always()
  description: Always cleanup, even after failures
```

### `steps.<step_id>.status`
Access the status of a specific step by its ID. Status values:
- `'success'` - Step completed successfully
- `'failure'` - Step failed with an error
- `'skipped'` - Step was skipped due to condition
- `'not_run'` - Step hasn't executed yet

```yaml
- id: test
  step: Run Tests

- id: deploy
  step: Deploy
  if: steps.test.status == 'success'
  description: Deploy only if tests passed
```

## Complex Conditions

Combine conditions using logical operators:

### AND Operator (`&&`)
```yaml
- id: conditional_step
  step: Some Action
  if: success() && steps.build.status == 'success'
  description: Runs if all succeeded AND build specifically succeeded
```

### OR Operator (`||`)
```yaml
- id: notify
  step: Send Notification
  if: failure() || steps.critical_check.status == 'failure'
  description: Notify on any failure or specific critical check failure
```

### NOT Operator (`not`)
```yaml
- id: fallback
  step: Use Fallback
  if: not steps.primary.status == 'success'
  description: Use fallback if primary didn't succeed
```

### Inequality (`!=`)
```yaml
- id: conditional
  step: Some Action
  if: steps.optional.status != 'skipped'
  description: Only if optional step was not skipped
```

### `steps.<step_id>.result`
Access the return value/result data from a specific step. Steps may return data that can be used in conditions.

```yaml
- id: check_data
  step: Validate Data
  description: This step returns validation results

- id: process_if_valid
  step: Process Data
  if: steps.check_data.result != None
  description: Only process if validation returned data

- id: conditional_on_value
  step: Handle Response
  if: steps.check_data.result != None && steps.check_data.status == 'success'
  description: Combine result check with status check
```

**Note**: The `result` field accesses the return value/details from the step execution. Use `!= None` to check if a step returned any data.

## Complete Example

```yaml
name: Conditional Workflow Demo
description: Full example demonstrating all conditional features

steps:
  # Step 1: Initial setup - no condition, always runs
  - id: setup
    step: Setup Environment
    description: Initialize environment

  # Step 2: Build - runs after setup
  - id: build
    step: Build Application
    if: success()
    description: Build only if setup succeeded

  # Step 3: Test - runs if build succeeded
  - id: test
    step: Run Tests
    if: steps.build.status == 'success'
    description: Test only if build succeeded

  # Step 4: Deploy - complex condition
  - id: deploy
    step: Deploy Application
    if: success() && steps.test.status == 'success'
    description: Deploy only if everything passed including tests

  # Step 5: Rollback - runs on failure
  - id: rollback
    step: Rollback Deployment
    if: failure() && steps.deploy.status == 'failure'
    description: Rollback if deployment failed

  # Step 6: Notify success
  - id: notify_success
    step: Send Success Notification
    if: steps.deploy.status == 'success'
    description: Notify team of successful deployment

  # Step 7: Notify failure
  - id: notify_failure
    step: Send Failure Notification
    if: failure()
    description: Notify team if anything failed

  # Step 8: Cleanup - always runs
  - id: cleanup
    step: Cleanup Resources
    if: always()
    description: Always cleanup temporary resources

  # Step 9: Final report
  - id: report
    step: Generate Report
    if: steps.cleanup.status == 'success'
    description: Generate report after cleanup completes
```

## Evaluation Behavior

1. **Sequential Evaluation**: Conditions are evaluated just before the step runs, so they see the current state of all previous steps.

2. **Skip Propagation**: If a step is skipped, subsequent steps using `success()` will still see it as successful (skipped ≠ failed).

3. **Early Termination**: If all remaining steps have conditions that can never be true, evaluation may stop early.

4. **Status Access**: You can only reference steps that have already executed or been skipped.

## Common Patterns

### Cleanup on Error
```yaml
- id: error_cleanup
  step: Cleanup After Error
  if: failure()
```

### Conditional Retry
```yaml
- id: retry
  step: Retry Operation
  if: steps.first_attempt.status == 'failure'
```

### Fork-Join Pattern
```yaml
# Fork
- id: path_a
  step: Path A
  if: steps.condition.status == 'success'

- id: path_b
  step: Path B
  if: steps.condition.status == 'failure'

# Join
- id: merge
  step: Merge Results
  if: steps.path_a.status == 'success' || steps.path_b.status == 'success'
```

### Multiple Fallbacks
```yaml
- id: primary
  step: Primary Method

- id: fallback1
  step: Fallback Method 1
  if: steps.primary.status == 'failure'

- id: fallback2
  step: Fallback Method 2
  if: steps.fallback1.status == 'failure'
```

## Tips and Best Practices

1. **Use Descriptive Step IDs**: Make step IDs clear since they're used in conditions.

2. **Document Complex Conditions**: Add descriptions explaining why a condition exists.

3. **Test Both Paths**: Ensure your workflow handles both success and failure paths.

4. **Always Cleanup**: Use `if: always()` for cleanup steps to prevent resource leaks.

5. **Avoid Circular Dependencies**: Don't create conditions that depend on steps that haven't run yet.

6. **Keep It Simple**: Complex conditions can be hard to debug; break into multiple simpler steps when possible.
