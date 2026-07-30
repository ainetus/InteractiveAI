#!/bin/bash

# Copyright (c) 2022, RTE (http://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of the OperatorFabric project.

# This starts by moving to the directory where the script is located so the paths below still work even if the script
# is called from another folder
cd "$(dirname "${BASH_SOURCE[0]}")"

url=$1 
if [[ -z $url ]]
then
	url="http://localhost"
fi
(
	cd bundles
	./deleteAllBundles.sh $url
	./loadAllBundles.sh $url
	cd ../processGroups
	./loadProcessGroups.sh cabProcessGroup.json $url
	#TODO Clear perimeters first?
	cd ../perimeters
	./createAllPerimeter.sh $url
	cd ../realTimeScreens
	./loadRealTimeScreens.sh realTimeScreens.json $url
	cd ../cabUsecasesEvent
	./loadEventServicesUseCase.sh $url
	cd ../cabUsecasesContext
	./loadContextServicesUseCase.sh $url
	cd ../cabUsecasesRecommendation
	./loadRecommendationServicesUseCase.sh $url

	# Assign entities to publisher_test so the UI shows entity selection cards
	# (cwd here is resources/cabUsecasesRecommendation, so getToken.sh is one level up)
	source ../getToken.sh "admin" $url
	echo "Assigning entities to publisher_test"
	curl -s -X PUT $url:3200/users/users/publisher_test \
	  -H "Content-Type: application/json" \
	  -H "Authorization: Bearer $token" \
	  -d '{"login":"publisher_test","entities":["PowerGrid","ATM","Railway"],"groups":["Dispatcher","ReadOnly","Supervisor"]}'
	echo ""
)
