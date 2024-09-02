import requests
from dotenv import load_dotenv, find_dotenv
import json
import arrow
import time
from dataclasses import asdict
from rid_definitions import LatLngPoint, RIDOperatorDetails, UASID, OperatorLocation, UAClassificationEU

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

class ArgonServerUploader:
    
    def __init__(self, credentials, resources):
        self.credentials = credentials
        self.resources = resources
    
    def upload_flight_declaration(self, filename):
        print ("dbg 10")
        with open(filename, "r") as flight_declaration_file:
            f_d = flight_declaration_file.read()
        
        print ("dbg 20")
        flight_declaration = json.loads(f_d)
        now = arrow.now()
        print ("dbg 30")
        one_minute_from_now = now.shift(minutes=1)
        four_minutes_from_now = now.shift(minutes=4)
        print ("dbg 40")

        # Update start and end time 
        flight_declaration['start_datetime'] = one_minute_from_now.isoformat()
        flight_declaration['end_datetime'] = four_minutes_from_now.isoformat()
        print ("dbg 50")
        headers = {"Content-Type": 'application/json', "Authorization": "Bearer " + self.credentials['access_token']}
        securl = self.resources['urls']['set_flight_declaration']
        print ("dbg 60")
        response = requests.post(securl, json=flight_declaration, headers=headers)
        print ("dbg 70")
        return response
    
    def update_operation_state(self, operation_id: str, new_state: int):
        print ("dbg 1")
        headers = {"Content-Type": 'application/json', "Authorization": "Bearer " + self.credentials['access_token']}
        print ("dbg 2")
        payload = {"state": new_state, "submitted_by": "hh@auth.com"}
        print ("dbg 3")
        securl = self.resources['urls']['update_flight_declaration_state'].format(operation_id=operation_id)
        print ("dbg 4")
        response = requests.put(securl, json=payload, headers=headers)
        print ("dbg 5")
        return response

    def delete_flight_declaration(self, operation_id: str):
        headers = {"Content-Type": 'application/json', "Authorization": "Bearer " + self.credentials['access_token']}
        securl = self.resources['urls']['del_flight_declaration'].format(operation_id=operation_id)
        response = requests.delete(securl, headers=headers)
        return response
        
    def submit_telemetry(self, filename, operation_id):
        with open(filename, "r") as rid_json_file:
            rid_json = rid_json_file.read()
            
        rid_json = json.loads(rid_json)
        states = rid_json['current_states']
        
        uas_id = UASID(
            registration_id=self.resources['uas']['registration_id'],
            serial_number=self.resources['uas']['serial_number'],
            utm_id=self.resources['uas']['utm_id']
        )
        eu_classification = UAClassificationEU()
        operator_location = OperatorLocation(
            position=LatLngPoint(
                lat=self.resources['operator']['lat'],
                lng=self.resources['operator']['lng']
            )
        )
        rid_operator_details = RIDOperatorDetails(
            id=operation_id,
            uas_id=uas_id,
            operation_description="Medicine Delivery",
            operator_id=self.resources['operator']['operator_id'],
            eu_classification=eu_classification,            
            operator_location=operator_location
        )
        for state in states: 
            headers = {"Content-Type": 'application/json', "Authorization": "Bearer " + self.credentials['access_token']}
            payload = {
                "observations": [{
                    "current_states": [state], 
                    "flight_details": {
                        "rid_details": asdict(rid_operator_details), 
                        "aircraft_type": "Helicopter",
                        "operator_name": "Thomas-Roberts"
                    }
                }]
            }
            securl = self.resources['urls']['set_telemetry']
            try:
                response = requests.put(securl, json=payload, headers=headers)
            except Exception as e:
                print(e)
            else:
                if response.status_code == 201:
                    print("Sleeping 3 seconds..")
                    time.sleep(3)
                else: 
                    print(response.json())


