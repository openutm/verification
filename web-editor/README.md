# OpenUTM Scenario Editor

A browser-based editor to design verification scenarios as a Directed Acyclic Graph (DAG).

## Features

- **Visual DAG Editor**: Design scenarios using a node-based interface powered by @xyflow/react.
- **Drag and Drop**: Easily add steps from the toolbox to the canvas.
- **Parameter Configuration**: Edit node parameters using a dedicated properties panel.
- **Scenario Execution**: Run scenarios directly in the editor and view results.
- **Import/Export**: Save and load scenarios as JSON files.
- **Dark Mode**: "Premium" developer-focused UI with theme toggling.
- **Responsive Layout**: Resizable panels and responsive design.

## Project Structure

The project follows a modular architecture separating concerns into components, hooks, and types:

- **`src/components/`**: UI components including the main `ScenarioEditor` and sub-components (`CustomNode`, `Toolbox`, `PropertiesPanel`, etc.).
- **`src/hooks/`**: Custom React hooks for logic isolation (`useScenarioGraph`, `useScenarioRunner`, `useScenarioFile`).
- **`src/types/`**: TypeScript definitions for strict type safety.
- **`src/styles/`**: CSS Modules for scoped styling.

## Getting Started

1. Install dependencies:

    ```bash
    npm install
    ```

2. Start the development server:

    ```bash
    npm run dev
    ```

3. Open your browser at `http://localhost:5173`.

## Tech Stack

- **React 19**: UI library.
- **TypeScript**: Static typing.
- **Vite**: Fast build tool.
- **@xyflow/react**: Graph visualization and interaction.
- **Lucide React**: Iconography.
- **CSS Modules**: Scoped styling.
