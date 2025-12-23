import inspect
from typing import Any, Dict, List, Optional, Union

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, create_model

from openutm_verification.server.runner import DynamicRunner, ScenarioDefinition, StepDefinition

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

runner = DynamicRunner()


@app.get("/")
async def root():
    return {"message": "OpenUTM Verification API is running"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/operations")
async def get_operations():
    return runner.get_available_operations()


@app.post("/session/reset")
async def reset_session():
    await runner.close_session()
    await runner.initialize_session()
    return {"status": "session_reset"}


@app.post("/run-scenario")
async def run_scenario(scenario: ScenarioDefinition):
    # For full scenario run, we might want a fresh runner or use the session one?
    # The original code created a new runner. Let's keep it that way for now,
    # or use the global one but reset session.
    # But DynamicRunner() creates a new instance.
    local_runner = DynamicRunner()
    try:
        results = await local_runner.run_scenario(scenario)
        return {"status": "completed", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Dynamic Route Generation
for class_name, client_class in runner.client_map.items():
    for name, method in inspect.getmembers(client_class):
        if hasattr(method, "_is_scenario_step"):
            step_name = getattr(method, "_step_name")

            # Create Pydantic model for parameters
            sig = inspect.signature(method)
            fields = {}
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                annotation = param.annotation
                if annotation == inspect.Parameter.empty:
                    annotation = Any
                else:
                    # Allow Dict for references (e.g. {"$ref": "..."})
                    annotation = Union[annotation, Dict[str, Any]]

                default = param.default
                if default == inspect.Parameter.empty:
                    fields[param_name] = (annotation, ...)
                else:
                    fields[param_name] = (annotation, default)

            # Create the model
            RequestModel = create_model(f"{class_name}_{name}_Request", __config__=ConfigDict(arbitrary_types_allowed=True), **fields)

            # Define the route handler
            # We need to capture class_name, name and RequestModel in the closure
            def create_handler(req_model, c_name, f_name):
                async def handler(body: req_model, run_in_background: bool = False, step_id: Optional[str] = None):
                    step_def = StepDefinition(
                        id=step_id, className=c_name, functionName=f_name, parameters=body.model_dump(), run_in_background=run_in_background
                    )
                    return await runner.execute_single_step(step_def)

                return handler

            handler = create_handler(RequestModel, class_name, name)

            # Register the route
            app.post(f"/api/{class_name}/{name}", response_model=Dict[str, Any], tags=[class_name], summary=step_name)(handler)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8989)
