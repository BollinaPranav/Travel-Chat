# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

from typing import Any, Text, Dict, List
import requests
import json
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.events import AllSlotsReset


class ActionSetFromLocation(Action):

    def name(self) -> Text:
        return "action_set_from_location"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        return [SlotSet("inform_from_location",self.from_text())]

class ActionSetToLocation(Action):

    def name(self) -> Text:
        return "action_set_to_location"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        return [{
            "inform_to_location": self.from_entity(entity="to_location", intent='inform_to_location')
        }]






class ActionSayFrom(Action):


    def name(self) -> Text:
        return "action_say_from"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        journey_preference = tracker.get_slot("journey_preference")
        public_transport_type = tracker.get_slot("public_transport_type")
        from_location = tracker.get_slot("inform_from_location")
        to_location = tracker.get_slot("inform_to_location")
        via_location = tracker.get_slot("via_location")
        journey_valid = True
        via = False


        # To check if the via location is worth going to, store the min time to go to the via location and then store
        # the min time required to go to final location, add them and compare only the original from and to without the via.

        original_from = from_location
        original_to = to_location
        min_fromvia = float(0)
        min_viato = float(0)
        min_time = float(0)
        response1 = ""
        response2 = ""
        if(via_location != "none" and via_location != "None"):
            via = True
            response1, min_fromvia = get_tfl_directions(from_location, via_location, journey_preference, public_transport_type, via)
            response1 += "-------------->> This was the via location provided:)"
            response2, min_viato = get_tfl_directions(via_location, to_location, journey_preference, public_transport_type, via)
            via = False
            response3, min_time = get_tfl_directions(original_from, original_to, journey_preference, public_transport_type, via)
            deviation = 0.2 * min_time
            if((min_fromvia + min_viato)<= (min_time + deviation)):
                response = response1 + response2
            else:
                journey_valid = False
                response, min_time = get_tfl_directions(from_location, to_location, journey_preference, public_transport_type, via)
        else:
            response, min_time = get_tfl_directions(from_location, to_location, journey_preference, public_transport_type, via)
        if(not journey_valid):
            response+= "the via location was too far"
        dispatcher.utter_message(text=f"Your from location is {from_location} and to location is {to_location}")
        dispatcher.utter_message(text=f"Your journey preference was: {journey_preference}")
        dispatcher.utter_message(text=f"Your transport preference was {public_transport_type}, via {via}, via_location {via_location}")
        dispatcher.utter_message(text=f"routes found: {response}")
        
        return [AllSlotsReset()]

def get_journey_info(journey, via):
    result = "   Journey details:\n"
    
    # Check if 'legs' is present in the journey
    legs = journey.get('legs', [])
    if not legs:
        result += "No legs information available for this journey.\n"
        return result
    
    for leg in legs:
        instruction = leg.get('instruction')
        steps = leg.get('steps', [])
        if steps:
            result += "\nSteps:\n"
            for step in steps:
                result += f"   - {step.get('description', 'N/A')} ({step.get('distance', 'N/A')} meters)\n"

        departure_point = leg.get('departurePoint', {}).get('commonName', {})
        arrival_point = leg.get('arrivalPoint', {}).get('commonName', {})
        result += f"  - From: {departure_point}\n"
        result += f"  - Summary: {instruction.get('summary')}\n"
        result += f"  - For a duration of: {leg.get('duration')} mins\n"
        result += f"  - You will be arriving at: {arrival_point}\n\n"
        instruction = leg.get('instruction')

        
        
    return result


def handle_response(response, from_location, to_location, journey_preference, public_transport_type, via):
    mintime = float(0)
    if response.status_code == 300:
        data = response.json()
        from_location_options = data.get('fromLocationDisambiguation', {}).get('disambiguationOptions', [])
        to_location_options = data.get('toLocationDisambiguation', {}).get('disambiguationOptions', [])

        from_location_naptan_ids = []
        to_location_naptan_ids = []

        # Choose the option with the highest match quality for each location
        for option in from_location_options:
            place = option.get('place', {})
            if place.get('$type') == 'Tfl.Api.Presentation.Entities.StopPoint, Tfl.Api.Presentation.Entities':
                naptan_id = place.get('naptanId')
                if naptan_id:
                    from_location_naptan_ids.append(naptan_id)

        for option in to_location_options:
            place = option.get('place', {})
            if place.get('$type') == 'Tfl.Api.Presentation.Entities.StopPoint, Tfl.Api.Presentation.Entities':
                naptan_id = place.get('naptanId')
                if naptan_id:
                    to_location_naptan_ids.append(naptan_id)

        # Check if further disambiguation is needed
        if from_location_naptan_ids and to_location_naptan_ids:
            # For simplicity, let's just use the first naptanId from each list
            from_location = from_location_naptan_ids[0]
            print(from_location)
            to_location = to_location_naptan_ids[0]
            print(to_location)
            response,mintime = get_tfl_directions(from_location, to_location, journey_preference, public_transport_type, via)

    # If no further disambiguation is needed, return the response as is
    return response,mintime





def get_tfl_directions(from_location, to_location, journey_preference, public_transport_type, via ):

    base_url = 'https://api.tfl.gov.uk/Journey/journeyresults/'
    if journey_preference == "any" and public_transport_type == "any":
        url = f"{base_url}{from_location}/to/{to_location}?timeis=arriving&journeypreference=leastinterchange&accessibilitypreference=norequirements&walkingspeed=slow&cyclepreference=none&bikeproficiency=easy&app_key=d1926b222a4f48689a4e2418fd86c039"
    elif journey_preference == "any":
        url = f"{base_url}{from_location}/to/{to_location}?timeis=arriving&mode={public_transport_type}&accessibilitypreference=norequirements&walkingspeed=slow&cyclepreference=none&bikeproficiency=easy&app_key=d1926b222a4f48689a4e2418fd86c039"
    elif public_transport_type == "any":
        url = f"{base_url}{from_location}/to/{to_location}?timeis=arriving&journeypreference={journey_preference}&accessibilitypreference=norequirements&walkingspeed=slow&cyclepreference=none&bikeproficiency=easy&app_key=d1926b222a4f48689a4e2418fd86c039"

    else:
        url = f"{base_url}{from_location}/to/{to_location}?timeis=arriving&journeypreference={journey_preference}&mode={public_transport_type}&accessibilitypreference=norequirements&walkingspeed=slow&cyclepreference=none&bikeproficiency=easy&app_key=d1926b222a4f48689a4e2418fd86c039"

    response = requests.get(url)
    if response.status_code == 300:
        print("300 ////")
        return handle_response(response, from_location, to_location,journey_preference, public_transport_type, via)

    # Print raw JSON response
    #print(json.dumps(response.json(), indent=2))  # Pretty print the JSON
    
    # Process the data
    data = response.json()
    json_file_path = "data2.json"
    # Write data to the JSON file
    minimumTimeJourney = float(0)

    if 'journeys' in data:
        journeys = data['journeys']
        result = " "
        result += f"Found {len(journeys)} route(s) to the destination:\n\n"
        result += "------------------------------------------------------------------------- \n"
        index = 0
        journey_dict = {}
        duration = ""


        for i, journey in enumerate(journeys):
            n = i + 1
            journey_name = f"Journey {n}"
            modes_list = []
            legs = journey.get('legs', [])
            duration = journey.get("duration")
            duration_list = []
            for leg in legs:
                mode = leg.get('mode')
                mode_type = mode.get('name')
                mode_duration = leg.get('duration')
                mode_distance = leg.get('distance')
                modes = {
                    "type": mode_type,
                    "duration": mode_duration,
                    "distance": mode_distance
                }
                modes_list.append(modes)
            journey_info = get_journey_info(journey, via)
            journey_details = {
                "name": journey_name,
                "duration": duration,
                "modeList": modes_list,
                "journey_info": journey_info

            }
            # result += f" Journey {n}:\n"
            # duration = journey.get("duration")
            #
            # result += f" - Duration of the journey: {duration}\n"
            # result += get_journey_info(journey, via)



            journey_dict[journey_name] = journey_details
        print(journey_dict)

        min_duration = float('inf')  # Initialize with a very large value
        min_duration_journey = None

        for journey_name, journey_details in journey_dict.items():
            duration = journey_details["duration"]
            modeList = journey_details["modeList"]
            if duration < min_duration:
                min_duration = duration
                min_duration_journey = journey_details
        minimumTimeJourney = min_duration_journey['duration']
        result += "Here's your recommended journey : \n"
        result += f" -Journey Name: {min_duration_journey['name']} \n"
        result += f" -Duration of the journey: {min_duration_journey['duration']} \n"
        result += " -Journey details: \n"
        result += f" {min_duration_journey['journey_info']} \n"
        result += "------------------------------------------------------------------------- \n"
        result += "Below are some more route recommendations based on your route choices \n\n"

        for i, journey in enumerate(journeys):

            n = i+1
            result += f" -Journey {n}:\n"
            duration = journey.get("duration")

            result += f" - Duration of the journey: {duration}\n"
            result += get_journey_info(journey, via)

        result += ("You have arrived at your destination :) \n")

       
    else:
        result = f"Error: {data.get('message', 'Please check the input')}"
    print (minimumTimeJourney)
    return result, minimumTimeJourney
        # 51.50722,-0.1275 '51.501,-0.123' '51.598806, -0.106944'
    #'51.50926403866,-0.1359197'





