from pathlib import Path

import yaml

# Define paths
BASE_DIR = Path(__file__).resolve().parents[1]
SCENARIOS_DIR = BASE_DIR / "scenarios"
DOCS_DIR = BASE_DIR / "docs" / "scenarios"


def format_title(name):
    return name.replace("_", " ").title()


def generate_markdown(scenario_data):
    name = scenario_data.get("name", "Unknown Scenario")
    description = scenario_data.get("description", "No description provided.")
    steps = scenario_data.get("steps", [])

    md_content = f"# {format_title(name)}\n\n"
    md_content += f"{description}\n\n"
    md_content += "## Steps Sequence\n\n"

    for idx, step in enumerate(steps, 1):
        step_name = step.get("step", "Unknown Step")
        step_id = step.get("id")
        step_desc = step.get("description")
        arguments = step.get("arguments")

        md_content += f"### {idx}. {step_name}\n"
        if step_desc:
            md_content += f"{step_desc}\n\n"

        if step_id:
            md_content += f"**ID:** `{step_id}`\n\n"

        if arguments:
            md_content += "**Arguments:**\n"
            for key, value in arguments.items():
                md_content += f"- `{key}`: {value}\n"
            md_content += "\n"
        else:
            md_content += "\n"

    return md_content


def main():
    if not SCENARIOS_DIR.exists():
        print(f"Scenarios directory not found: {SCENARIOS_DIR}")
        return

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    for yaml_file in sorted(SCENARIOS_DIR.rglob("*.yaml")):
        relative = yaml_file.relative_to(SCENARIOS_DIR)
        print(f"Processing {relative}...")
        try:
            with open(yaml_file, "r") as f:
                data = yaml.safe_load(f)

            if not data:
                print(f"Skipping empty file: {relative}")
                continue

            md_content = generate_markdown(data)

            md_filename = (DOCS_DIR / relative).with_suffix(".md")
            md_filename.parent.mkdir(parents=True, exist_ok=True)
            with open(md_filename, "w") as f:
                f.write(md_content)

            print(f"Generated {md_filename}")

        except Exception as e:
            print(f"Error processing {yaml_file.name}: {e}")


if __name__ == "__main__":
    main()
