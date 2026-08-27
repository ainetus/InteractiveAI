from pickle import FALSE
from time import sleep
import requests
import json
from datetime import datetime, timedelta


print("test")

# username = "railway_user"
username = "publisher_test"
password = "test"

# server_url = "192.168.210.29"
server_url = "localhost"
#server_url = "192.168.209.192:3200"

client_id = "opfab-client"
token_url = f"http://{server_url}:3200/auth/token"
events_url = f"http://{server_url}:3200/cab_event/api/v1/events"
context_url = f"http://{server_url}:3200/cabcontext/api/v1/contexts"

token_payload = f"username={username}&password={password}&grant_type=password&client_id={client_id}"
token_headers = {
    'Content-Type': 'application/x-www-form-urlencoded'
}
req_token = requests.post(token_url, headers=token_headers, data=token_payload)

print("Token status:", req_token.status_code)
print("Token response:", req_token.text[:200])

# Check if request was successful
if req_token.status_code > 500:
    raise ValueError(f"Token request failed with status code {req_token.status_code}")

# Extract and return access token
access_token = json.loads(req_token.text)['access_token']
token_type = json.loads(req_token.text)['token_type']
token =  token_type + ' ' + access_token


# event_payload1 = json.dumps({
# "criticality": "HIGH", #MEDIUM or LOW
#                     "title": "fake_title",
#                     "description": "fake_descp",
#                     "data": {
#                         #"simulation_name" : None,
#                         "event_type": "PASSENGER", #INFRASTRUCTURE or IMPACT or HARDWARE
#                         "id_train": "1234",
#                         "agent_id": "1",
#                         "delay": "1 hour"
#                         #"num_rame": None,
#                         #"tmp_rame": None,
#                         #"agent_position": None,
#                         #"malfunction_stop_position": None,
#                         #"travel_plan": None,
#                     },
#                     #"start_date": iso_date,
#                     #"end_date": iso_date,
#                     "use_case": "Railway"
# }
# )


# # event_data = {
# #                     "criticality": "HIGH", #MEDIUM or LOW
# #                     "title": "fake_itle"",
# #                     "description": "fake_descp",
# #                     "data": {
# #                         #"simulation_name" : None,
# #                         "event_type": "PASSENGER", #INFRASTRUCTURE or IMPACT or HARDWARE
# #                         "id_train": "1234",
# #                         #"agent_id": None,
# #                         #"num_rame": None,
# #                         #"tmp_rame": None,
# #                         #"agent_position": None,
# #                         #"malfunction_stop_position": None,
# #                         #"travel_plan": None,
# #                     },
# #                     "start_date": iso_date,
# #                     "end_date": iso_date,
# #                     "use_case": "Railway"
# #                 }




# context_payload1 = json.dumps({
# "data": {
#                 "trains": { # peut mettre plusieurs trains
#                         "id_train": "1234",
#                         #"nb_passengers_onboard": None,
#                         #"nb_passengers_connection": None,
#                         #"latitude": latitude,
#                         #"longitude": longitude,
#                         #"speed": None,
#                         "failure": "FALSE"
#                 }
#                 #"list_of_target": None,
#                 #"direction_agents": None,
#                 #"position_agents": None,
#             },
#             #"date": iso_date,
#             "use_case": "Railway",
# }
# )


# # context_data = {
# #             "data": {
# #                 "trains": { # peut mettre plusieurs trains
# #                         "id_train": "1234",
# #                         #"nb_passengers_onboard": None,
# #                         #"nb_passengers_connection": None,
# #                         "latitude": latitude,
# #                         "longitude": longitude,
# #                         #"speed": None,
# #                         "failure": FALSE
# #                 }
# #                 #"list_of_target": None,
# #                 #"direction_agents": None,
# #                 #"position_agents": None,
# #             },
# #             "date": iso_date,
# #             "use_case": "Railway",
# #         }

start_date = datetime.now() + timedelta(seconds=10)

event_payload1 = json.dumps({
"criticality": "HIGH", #MEDIUM or LOW
                    "title": "Passenger taken ill in Poitiers",
                    "description": "Passenger taken ill in TGV AB001. emergency services intervention in the Poitiers station. Impossible to access the Poitiers station. Estimated time of service traffic resumption : 12:00." ,
                    "data": {
                        #"simulation_name" : None,
                        "id_event": "1",
                        "event_type": "PASSENGER", #INFRASTRUCTURE or IMPACT or HARDWARE
                        "id_train": "AB001",
                        "agent_id": "1",
                        "delay": 0,
                        #"proba": "0.4"
                    },
                    "start_date": (start_date).isoformat(),
                    "end_date": (start_date + timedelta(hours=2)).isoformat(),
                    "use_case": "Railway"
}
)


context_payload1 = json.dumps({
"data": {
                "trains":[{ # peut mettre plusieurs trains
                        "id_train": "AB001",
                        "nb_passengers_onboard": 468,
                        "trip" : "Paris/Bordeaux",
                        "stops":"Poitiers/Bordeaux",
                        #"nb_passengers_connection": 0,
                        "latitude": 46.583328,
                        "longitude": 0.33333,
                        #"speed": None,
                        "failure": True
                }]
        },  
"use_case": "Railway"     
}         
)




# context_payload1 = json.dumps({
# "data": {
#                 "trains": { # peut mettre plusieurs trains
#                         "id_train": "1234",
#                         #"nb_passengers_onboard": None,
#                         #"nb_passengers_connection": None,
#                         #"latitude": latitude,
#                         #"longitude": longitude,
#                         #"speed": None,
#                         "failure": "FALSE"
#                 }
#                 #"list_of_target": None,
#                 #"direction_agents": None,
#                 #"position_agents": None,
#             },
#             #"date": iso_date,
#             "use_case": "Railway",
# }
# )



event_payload2 = json.dumps({
"criticality": "HIGH", #MEDIUM or LOW
                    "title": "Broken overhead wire",
                    "description": "Broken overhead wire for TGV CD001 in the Pliboux plant on line LGV SEA. The adjacent track is not accessible. Trains are rerouted to the standard line between Poitiers and Angoulême. Estimated time of service traffic resumption : 23:00",
                    "data": {
                        #"simulation_name" : None,
                        "id_event":"2",
                        "event_type": "INFRASTRUCTURE", #INFRASTRUCTURE or IMPACT or HARDWARE
                       "id_train": "AB001",
                        "latitude": "46.167",
                        "longitude": "0.127",
                        "agent_id": "1",
                        "delay":  0,
                        #"proba": "0.4"
                    },
                    "start_date": (start_date + timedelta(seconds=30)).isoformat(),
                    "end_date": (start_date + timedelta(hours=4)).isoformat(),
                    "use_case": "Railway"
}
)


context_payload2 = json.dumps({
"data": {
                "trains": [{ # peut mettre plusieurs trains
                        "id_train": "AB001",
                        "nb_passengers_onboard": "459",
                        "trip" : "Paris/Bordeaux",
                        "stops":"Angoulême/Bordeaux",
                        #"nb_passengers_connection": None,
                        #"latitude": latitude,
                        #"longitude": longitude,
                        #"speed": None,
                        "failure": False
                }]
        },  
"use_case": "Railway"     
}
)


event_payload3 = json.dumps({
"criticality": "HIGH", #MEDIUM or LOW
                    "title": "Gas leak",
                    "description": "Gas leak in the city of Bassens. The railway facility is in the scurity perimeter. Circulation is forbidden by authorities. Estimated time of traffic resumption : 19:00.",
                    "data": {
                        #"simulation_name" : None,
                        "event_type": "INFRASTRUCTURE", #INFRASTRUCTURE or IMPACT or HARDWARE
                        "id_event":"3",
                        "id_train": "EF004",
                        "latitude" : "44.900002",
                        "longitude" : "-0.51667 ",
                        "agent_id" : "1",
                        "delay": 0,
                        #"proba": "0.4"
                    },
                    "start_date": (start_date + timedelta(seconds=40)).isoformat(),
                    "end_date": (start_date + timedelta(hours=5)).isoformat(),
                    "use_case": "Railway"
}
)

context_payload3 = json.dumps({
"data": {
                "trains": [{ # peut mettre plusieurs trains
                        "id_train": "EF004",
                        "nb_passengers_onboard": "348",
                        "trip" : "Bordeaux / Paris",
                        "stops":"Bordeaux / Libourne/ Angoulême / Poitiers / Chatellerault",
                        #"nb_passengers_connection": None,
                        #"latitude": latitude,
                        #"longitude": longitude,
                        #"speed": None,
                        "failure": False
                }]
        },  
"use_case": "Railway"     
}
)


event_headers = {
            'Authorization': token,
            'Content-Type': 'application/json'
        }
# Les contexts


sleep(10)
response11 = requests.request('POST', context_url, headers=event_headers, data=context_payload1)
response12 = requests.request('POST', events_url, headers=event_headers, data=event_payload1)

print("Context status:", response11.status_code, response11.text)
print("Event status:", response12.status_code, response12.text)




sleep(10)

response21 = requests.request('POST', context_url, headers=event_headers, data=context_payload2)
response22 = requests.request('POST', events_url, headers=event_headers, data=event_payload2)

print("Context status:", response21.status_code, response21.text)
print("Event status:", response22.status_code, response22.text)



sleep(5)

response31 = requests.request('POST', context_url, headers=event_headers, data=context_payload3)
response32 = requests.request('POST', events_url, headers=event_headers, data=event_payload3)

print("Context status:", response31.status_code, response31.text)
print("Event status:", response32.status_code, response32.text)