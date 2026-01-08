# F3 Non Conforming Path

Verifies the system's ability to detect and handle a non-conforming flight.  The flight deviates from its declared intent, and we expect the system  to transition the operation state to NONCONFORMING.


## Steps Sequence

### 1. Setup Flight Declaration
Initializes the flight declaration.


### 2. Update Operation State
Activates the operation.

### 3. Wait 5 seconds
Pauses execution to allow initial state propagation.

### 4. Submit Telemetry for 20 seconds
Sends telemetry updates that intentionally deviate from the plan.

### 5. Check Operation State
Verifies that the system has correctly identified the Non-Conforming state.

### 6. Update Operation State
Ends the operation.

### 7. Teardown Flight Declaration
Cleanup.
