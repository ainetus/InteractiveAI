
import json


################################################################
######### Event 1 Recommendations ##############################
################################################################

Reco11 = json.dumps({
"data": {
                "title": "Stay at the St Pierre des Corps station",
                "description" : "Hold the train in the St Pierre des Corps station until traffic resumes.",
                "use_case": "Railway",
                "agent_type": "AI",
                "kpis": {
                        "cost" : "78",
                        "nb_impacted_passengers" : "468",
                        "total_cost" : "32838",
                        "delay" : "1h30",
                        "best": "True",
                        }
                    
        }
}
)

Reco12 = json.dumps({
"data": {
                "title": "Delay",
                "description" : "Hold the train on the track until traffic resumes. Arrangements for passenger support.",
                "use_case": "Railway",
                "agent_type": "AI",
                "kpis": {
                        "cost" : "87",
                        "nb_impacted_passengers" : "398",
                        "total_cost" : "34626",
                        "delay" : "1h30",
                        "best": "False",
                        }
                    
        }
}
)


Reco13 = json.dumps({
"data": {
                "title": "Reroute",
                "description" : "Reroute the trains. Passengers traveling to and from Poitiers are being assisted.",
                "use_case": "Railway",
                "agent_type": "AI",
                "kpis": {
                        "cost" : "102",
                        "nb_impacted_passengers" : "350",
                        "total_cost" : "35700",
                        "delay" : "1h40",
                        "best": "False",
                        }
                    
        }
}
)


Reco14 = json.dumps({
"data": {
                "title": "Cancel",
                "description" : "Train services are cancelled. Passengers are advised to postpone their journey.",
                "use_case": "Railway",
                "agent_type": "AI",
                "kpis": {
                        "cost" : "233",
                        "nb_impacted_passengers" : "468",
                        "total_cost" : "109044",
                        "delay" : "1h45",
                        "best": "False",
                        }
                    
        }
}
)

################################################################
######### Event 2 Recommendations ##############################
################################################################


Reco21 = json.dumps({
"data": {
                "title": "Stay at the station",
                "description" : "Hold the train in the Poitiers station until traffic resumes.",
                "use_case": "Railway",
                "agent_type": "AI",
                "kpis": {
                        "cost" : "123",
                        "nb_impacted_passengers" : "459",
                        "total_cost" : "56457",
                        "delay" : "1h05",
                        "best": "False",
                        }
                    
        }
}
)





Reco22 = json.dumps({
"data": {
                "title": "Delay",
                "description" : "Hold the train on the track until traffic resumes. Arrangements for passenger support.",
                "use_case": "Railway",
                "agent_type": "AI",
                "kpis": {
                        "cost" : "129",
                        "nb_impacted_passengers" : "459",
                        "total_cost" : "59211",
                        "delay" : "1h00",
                        "best": "False",
                        }
                    
        }
}
)

Reco23 = json.dumps({
"data": {
                "title": "Reroute",
                "description" : "Diversion and rerouting of trains to the standard line between Angoulême and Poitiers. ",
                "use_case": "Railway",
                "agent_type": "AI",
                "kpis": {
                        "cost" : "73",
                        "nb_impacted_passengers" : "459",
                        "total_cost" : "33507",
                        "delay" : "1h00",
                        "best": "True",
                        }
                    
        }
}
)


Reco24 = json.dumps({
"data": {
                "title": "Cancel",
                "description" : "Train services are cancelled. Passengers are advised to postpone their journey.",
                "use_case": "Railway",
                "agent_type": "AI",
                "kpis": {
                        "cost" : "221",
                        "nb_impacted_passengers" : "459",
                        "total_cost" : "101439",
                        "delay" : "1h00",
                        "best": "False",
                        }
                    
        }
}
)


################################################################
######### Event 3 Recommendations ##############################
################################################################

Reco31 = json.dumps({
"data": {
                "title": "Wait at the Bordeaux station",
                "description" : "Hold the train at the station until traffic resumes.",
                "use_case": "Railway",
                "agent_type": "AI",
                "kpis": {
                        "cost" : "94",
                        "nb_impacted_passengers" : "348",
                        "total_cost" : "32712",
                        "delay" : "00h30",
                        "best": "True",
                        }
                    
        }
}
)


Reco32 = json.dumps({
"data": {
                "title": "Delay",
                "description" : "Hold the train on the track until traffic resumes. Arrangements for passenger support.",
                "use_case": "Railway",
                "agent_type": "AI",
                "kpis": {
                        "cost" : "94",
                        "nb_impacted_passengers" : "317",
                        "total_cost" : "32618",
                        "delay" : "00h53",
                        "best": "False",
                        }
                    
        }
}
)


Reco33 = json.dumps({
"data": {
                "title": "Rerouting from Bordeaux to Angoulême ",
                "description" : "Diversion and rerouting of trains to the standard line between Angoulême and Poitiers.",
                "use_case": "Railway",
                "agent_type": "AI",
                "kpis": {
                        "cost" : "95",
                        "nb_impacted_passengers" : "348",
                        "total_cost" : "33060",
                        "delay" : "1h24",
                        "best": "False",
                        }
                    
        }
}
)

Reco34 = json.dumps({
"data": {
                "title": "Supprimer",
                "description" : "Train services are cancelled. Passengers are advised to postpone their journey.",
                "use_case": "Railway",
                "agent_type": "AI",
                "kpis": {
                        "cost" : "257",
                        "nb_impacted_passengers" : "348",
                        "total_cost" : "89436",
                        "delay" : "00h40",
                        "best": "False",
                        }
                    
        }
}
)


################################################################
######### Events 4 to 10 #######################################
################################################################
# Matching the events of usecases_examples/Railway/railway_mock_simulator.py.
# Each one trades the KPIs off differently, with ties on some of them, so that
# the KPI an operator picks - and their order of importance - changes the ranking.
# cost is per impacted passenger: total_cost = cost * nb_impacted_passengers.


def _reco(title, description, cost, passengers, delay, best=False):
    return json.dumps({
        "data": {
            "title": title,
            "description": description,
            "use_case": "Railway",
            "agent_type": "AI",
            "kpis": {
                "cost": str(cost),
                "nb_impacted_passengers": str(passengers),
                "total_cost": str(cost * passengers),
                "delay": delay,
                "best": str(best),
            },
        }
    })


# 4. Signalling failure near Poitiers (TGV 8541)
Recos4 = [
    _reco("Run on sight through the section",
          "Drive through the failed section at reduced speed under the signaller's written authorisation.",
          64, 455, "0h50", best=True),
    _reco("Divert via the classic line",
          "Leave the high-speed line at the next junction and run on the classic Tours - Poitiers line.",
          88, 455, "1h10"),
    _reco("Hold at Poitiers until repair",
          "Stop at Poitiers and wait for the maintenance team to restore the signalling.",
          71, 455, "1h35"),
    _reco("Terminate at Poitiers, bus bridge",
          "End the journey at Poitiers; passengers travelling beyond are taken on by coaches.",
          140, 210, "2h00"),
]

# 5. Fallen tree on the track near Chatellerault (TGV 8507)
Recos5 = [
    _reco("Clear the track, then resume",
          "Send the track crew to remove the tree, then resume at line speed after inspection.",
          52, 380, "0h45", best=True),
    _reco("Reverse to Chatellerault and wait",
          "Bring the train back to Chatellerault station, where passengers can be looked after, until the line reopens.",
          58, 380, "0h55"),
    _reco("Single-line working on the adjacent track",
          "Switch to the other track and run both directions on it past the obstacle.",
          61, 380, "0h25"),
    _reco("Transfer passengers to the following train",
          "Passengers for Poitiers and beyond board the following TGV, which runs on the adjacent track.",
          95, 150, "0h40"),
]

# 6. Heat-related speed restriction near Angouleme (TGV 8547)
Recos6 = [
    _reco("Run at 160 km/h through the restricted section",
          "Respect the temporary speed restriction and keep the timetable for the other stops.",
          18, 502, "0h15", best=True),
    _reco("Reschedule the following trains' paths",
          "Retime the trains behind so that the restriction does not ripple down the line.",
          25, 502, "0h10"),
    _reco("Skip the Angouleme stop to recover time",
          "Run through Angouleme without stopping; its passengers are rebooked on the next train.",
          40, 85, "0h05"),
    _reco("Hold until track inspection",
          "Stop the train until the track has been inspected and the restriction lifted.",
          33, 502, "0h40"),
]

# 7. Pantograph damage, TGV 8555 stranded near Tours
Recos7 = [
    _reco("Rescue locomotive to St Pierre des Corps",
          "A diesel rescue locomotive tows the train to St Pierre des Corps, where passengers change trains.",
          112, 430, "1h50", best=True),
    _reco("Evacuate onto a relief train",
          "A relief train pulls up on the adjacent track and passengers cross over with the staff's help.",
          135, 430, "1h15"),
    _reco("Couple the following TGV and push",
          "The following TGV couples to the stranded train and pushes it to the next station.",
          98, 430, "2h10"),
    _reco("Cancel and rebook",
          "The train is cancelled once towed; passengers are refunded and rebooked on later trains.",
          210, 430, "3h00"),
]

# 8. Door fault at Poitiers station (TGV 8521)
Recos8 = [
    _reco("Lock out the faulty door and depart",
          "Isolate the door, signpost it on the platform and leave with the other doors.",
          8, 289, "0h08", best=True),
    _reco("Repair on the platform",
          "The on-call technician repairs the door before departure.",
          12, 289, "0h25"),
    _reco("Swap to a reserve trainset",
          "Passengers move to the reserve trainset waiting at Poitiers.",
          55, 289, "0h45"),
    _reco("Lock out the door, staff in the coach",
          "Isolate the door and have a member of staff stay in the coach until the next stop.",
          15, 289, "0h08"),
]

# 9. Unattended baggage, security perimeter at Bordeaux St Jean (TGV 8537)
Recos9 = [
    _reco("Hold outside the station",
          "Stop before the station until the police lift the alert.",
          47, 520, "0h45", best=True),
    _reco("Divert to a platform outside the perimeter",
          "Run into a platform away from the security perimeter; passengers leave by the side exit.",
          53, 520, "0h20"),
    _reco("Terminate at Libourne, shuttle buses",
          "End the journey at Libourne; coaches take passengers on to Bordeaux.",
          90, 520, "1h05"),
    _reco("Stop at Cenon, tram to the city centre",
          "Make an extra stop at Cenon; passengers for central Bordeaux continue by tram.",
          39, 260, "0h35"),
]

# 10. Knock-on delay threatening connections at Bordeaux (TGV 8561)
Recos10 = [
    _reco("Hold the connecting trains",
          "Ask the regional trains leaving Bordeaux to wait for the TGV's connecting passengers.",
          30, 410, "0h25", best=True),
    _reco("Let connections leave, rebook passengers",
          "Connecting trains leave on time; the passengers who miss them are rebooked and assisted.",
          44, 180, "0h25"),
    _reco("Recover time with a shorter dwell",
          "Shorten the stops at Poitiers and Angouleme to make up part of the delay.",
          36, 410, "0h35"),
    _reco("Run at line speed, skip Angouleme",
          "Skip the Angouleme stop to arrive in time; its passengers take the following train.",
          52, 95, "0h10"),
]


RECOMMENDATION_CATALOG = {
    "1": [Reco11, Reco12, Reco13, Reco14],
    "2": [Reco21, Reco22, Reco23, Reco24],
    "3": [Reco31, Reco32, Reco33, Reco34],
    "4": Recos4,
    "5": Recos5,
    "6": Recos6,
    "7": Recos7,
    "8": Recos8,
    "9": Recos9,
    "10": Recos10,
}
