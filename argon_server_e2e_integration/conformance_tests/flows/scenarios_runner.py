import sys
import yaml
import json
import os
import threading
import time
from os.path import dirname, abspath

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auth_factory import NoAuthCredentialsGetter
from run_f1_flow import ArgonServerUploader

class FlightScenarioRunner:
    def __init__(self, resources):
        self.resources = resources
        self.my_credentials = NoAuthCredentialsGetter()
        self.credentials = self.my_credentials.get_cached_credentials(
            audience=resources['audience'], 
            scopes=resources['scopes']
        )
        self.parent_dir = dirname(abspath(__file__))
        self.uploader = ArgonServerUploader(credentials=self.credentials, resources=self.resources)

    def run_scenario(self, scenario):
        operation_id = None
        scenario_success = True
        for step in scenario['steps']:
            sub_flow = step['sub_flow']
            input_file = step.get('input', '')
            abs_file_path = os.path.join(self.parent_dir, input_file) if input_file else ''
            new_state = step.get('new_state', '')

            try:
                response = self.execute_step(sub_flow, abs_file_path, operation_id, new_state)
                if not self.handle_response(response, step, operation_id):
                    scenario_success = False
                    break
                if sub_flow == 'upload_flight_declaration' and response.status_code == 200:
                    operation_id = response.json().get('id')
            except Exception as e:
                print(f"Error in {sub_flow}: {str(e)}")
                scenario_success = False
                break

        return scenario_success

    def execute_step(self, sub_flow, abs_file_path, operation_id, new_state):
        print("Executing step: ", sub_flow)
        if sub_flow == 'upload_flight_declaration':
            response = self.uploader.upload_flight_declaration(filename=abs_file_path)
            time.sleep(2)
            return response
        elif sub_flow == 'update_operation_state' and operation_id:
            response = self.uploader.update_operation_state(operation_id=operation_id, new_state=new_state)
            time.sleep(2)
            return response
        elif sub_flow == 'submit_telemetry' and operation_id:
            thread = threading.Thread(target=self.uploader.submit_telemetry, args=(abs_file_path, operation_id,))
            thread.start()
            print("Telemetry submission for 30 seconds...")
            time.sleep(30)
            #thread.join()
            print("Telemetry submission completed.")
            return None  # Return None as submit_telemetry does not provide a response directly
        elif sub_flow == 'del_flight_declaration' and operation_id:
            print ("calling delete_flight_declaration on declaration_id: ", operation_id)
            response = self.uploader.delete_flight_declaration(operation_id=operation_id)
            return response

        raise ValueError("Invalid sub_flow or missing operation_id")

    def handle_response(self, response, step, operation_id):
        if response is None:  # For sub_flows like submit_telemetry where there's no direct response
            return True

        if response.status_code == 204: # delete_flight_declaration sends 204 success code
            return True

        if response.status_code == 200:
            data = response.json()
            state = data.get('state')
            expected_state = step.get('expected_state')
            if state == expected_state or expected_state is None:
                print(f"{step['sub_flow']} successful: {data}")
                return True
            else:
                print(f"State mismatch in {step['sub_flow']}: expected {expected_state}, got {state}")
        else:
            print(f"Error in {step['sub_flow']}: {response.json()}")

        response = self.uploader.delete_flight_declaration(operation_id=operation_id)
        if response.status_code == 200:
            print ("Tear down for the flight declaration complete.")
        else:
            print ("Tear down for the flight declaration failed.")

        return False

def load_scenarios(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

if __name__ == '__main__':
    scenarios = load_scenarios('scenarios.yaml')
    resources = scenarios['resources']
    scenario_runner = FlightScenarioRunner(resources=resources)
    all_scenarios_success = True

    for scenario in scenarios['scenarios']:
        print(f"Running scenario {scenario['flow']}...")
        if scenario_runner.run_scenario(scenario):
            print(f"Scenario {scenario['flow']} succeeded.\n")
        else:
            print(f"Scenario {scenario['flow']} failed.\n")
            all_scenarios_success = False

    if all_scenarios_success:
        print("All scenarios completed successfully.")
    else:
        print("Some scenarios failed.")
