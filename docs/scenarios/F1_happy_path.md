# F1 Happy Path

This scenario verifies the nominal flow (Happy Path) for a flight operation.  It walks through the lifecycle of a flight from declaration to activation,  submission of telemetry, and finally ending the operation.


## Steps Sequence

### 1. Setup Flight Declaration
Creates a fresh flight declaration in the DSS.

### 2. Activate Operation State
Activates the flight operation, transitioning it to the active state.

### 3. Submit Telemetry
Simulates the broadcast of telemetry data for 30 seconds.

### 4. End Operation State
Marks the operation as ended after the flight is complete.

### 5. Teardown Flight Declaration
Cleans up the flight declaration and any associated resources.
