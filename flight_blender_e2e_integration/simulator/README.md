# Simulator

This folder contains tools and scripts for running flight simulations. The simulations are designed to generate realistic flight data for testing and integration purposes.

## Running the `adjacent_circular_flights_simulation`

The `adjacent_circular_flights_simulation` generates flight paths that simulate adjacent circular flight patterns. Follow the steps below to run the simulation:

### Prerequisites
1. Ensure you have Python 3.8+ installed.
2. Install the required dependencies by running:
    ```bash
    pip install -r requirements.txt
    ```

### Steps to Run
1. Navigate to the simulator directory:
    ```bash
    cd verification/flight_blender_e2e_integration/simulator
    ```
2. Run the simulation script:
    ```bash
    python adjacent_circular_flights_simulation.py
    ```
3. The simulation will generate flight data and output it to the `output` directory.

### Output
The generated flight data will be stored in JSON format in the `output` directory. This data can be used for further analysis or integration testing.

For more details, refer to the comments in the `adjacent_circular_flights_simulation.py` script.
This repository uses files / data from the `interuss/monitoring` repository to build simulation data