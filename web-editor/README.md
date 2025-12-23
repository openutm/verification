# OpenUTM Scenario Editor

A browser-based editor to design verification scenarios as a Directed Acyclic Graph (DAG).

## Features

- **Visual DAG Editor**: Design scenarios using a node-based interface powered by @xyflow/react.
- **Drag and Drop**: Easily add steps from the toolbox to the canvas.
- **Parameter Configuration**: Edit node parameters using a dedicated properties panel.
- **Scenario Execution**: Run scenarios directly in the editor with real-time visual feedback (running, success, failure) and view results.
- **Import/Export**: Save and load scenarios as JSON files.
- **Dark Mode**: "Premium" developer-focused UI with theme toggling and optimized contrast.
- **Enhanced UX**: Clear node selection states and hover effects designed for usability.
- **Responsive Layout**: Resizable panels and responsive design.

## Project Structure

The project follows a modular architecture separating concerns into components, hooks, and types:

- **`src/components/`**: UI components including the main `ScenarioEditor` and sub-components (`CustomNode`, `Toolbox`, `PropertiesPanel`, etc.).
- **`src/hooks/`**: Custom React hooks for logic isolation (`useScenarioGraph`, `useScenarioRunner`, `useScenarioFile`).
- **`src/types/`**: TypeScript definitions for strict type safety.
- **`src/styles/`**: CSS Modules for scoped styling.

## Backend Setup

The editor requires the backend server to be running to fetch available operations and execute scenarios.

### Start the Backend Server

The editor communicates with a local Python server to retrieve the list of available scenario steps (operations) and to execute them.

Run the server from the project root:

```bash
uv run src/openutm_verification/server/main.py
```

The server will start on `http://0.0.0.0:8989`.

## Getting Started (Frontend)

1. Navigate to the `web-editor` directory:

    ```bash
    cd web-editor
    ```

2. Install dependencies:

    ```bash
    npm install
    ```

3. Start the development server:

    ```bash
    npm run dev
    ```

4. Open your browser at `http://localhost:5173`.

## Tech Stack

- **React 19**: UI library.
- **TypeScript**: Static typing.
- **Vite**: Fast build tool.
- **@xyflow/react**: Graph visualization and interaction.
- **Lucide React**: Iconography.
- **CSS Modules**: Scoped styling.
