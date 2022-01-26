/*
 * Copyright 2019 Google LLC. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { Loader } from '@googlemaps/js-api-loader';

const loader = new Loader({
  apiKey: "GOOGLE_API_KEY",
  version: "weekly",
});

let map;
let granualrityPath = 0.0001;
let deltaForContinuity: number = 0.00001;
declare var google;
let changetm: any = null;

const Sidewalk = "Sidewalk"
const Detached_Sidewalk = "Detached Sidewalk"
const No_Sidewalk = "No Sidewalk"

let sidewalkColorMap = {}
// sidewalkColorMap[Sidewalk] = "#008000"
// sidewalkColorMap[Detached_Sidewalk] = "#FF7F00"

sidewalkColorMap[Sidewalk] = "#FF7F00"
sidewalkColorMap[Detached_Sidewalk] = "#00cc33"

sidewalkColorMap[No_Sidewalk] = "#FF0000"

// function to create the checkboxes on the maps
function CreateBox(text) {
  let ListElement = document.createElement("li");
  let InputElement = document.createElement("input");
  InputElement.setAttribute("type", "checkbox");
  InputElement.id = text;
  InputElement.checked = true;
  InputElement.addEventListener('click', function () {
    toggleLines(text, this.checked);
  });

  let LabelElement = document.createElement("label");
  LabelElement.setAttribute("for", text);
  LabelElement.style.color = "black";
  LabelElement.style.content = "\\00D7";
  LabelElement.style.backgroundColor = sidewalkColorMap[text];
  LabelElement.innerHTML = text;

  ListElement.appendChild(InputElement);
  ListElement.appendChild(LabelElement);

  return ListElement;

};

let allSideWalks = [] as any;
let allSideWalkPaths;

// function to toggle visibility of the sidewalk lines on the maps based on the checkboxes.
function toggleLines(colorKey, visible) {
  try {
    // console.log(allSideWalkPaths);
    let current = allSideWalkPaths[sidewalkColorMap[colorKey]];
    // console.log(colorKey);
    // console.log(current);
    // current[0].setVisible(visible);
    if(current.length>0)
    current.forEach(line => {
      // console.log(line);
      // console.log(visible);
      line.setVisible(visible);
      // line.setMap(null);
    });
  } catch (e) { console.warn(e) }

};

/* checks if the point created using granularityPath (in function drawOnMap) lies within a specific distance of the next available lat-long to create a continuous graph */
function checkForContiguousPoint(currentCoords, AvailablePoints): Array<number> {
  // console.log("cont");
  // console.log(currentCoords);
  // console.log(AvailablePoints);
  let lat = currentCoords[0];
  let lng = currentCoords[1];
  let prevDist = Number.MAX_VALUE;
  AvailablePoints.forEach(element => {
    // console.log(element[0]);
    if (currentCoords[0] != element[0] || currentCoords[1] != element[1]) {
      // console.log("continuous point: not same coords");
      let latDist: number = Number(Math.abs(currentCoords[0] - element[0]).toPrecision(6));
      let lngDist: number = Number(Math.abs(currentCoords[1] - element[1]).toPrecision(6));
      // console.log(latDist+" & "+Math.abs(lngDist)+" <= "+deltaForContinuity);
      if (latDist <= deltaForContinuity && lngDist <= deltaForContinuity) {
        // console.log("continuous point: closer dist");
        let minDist = Math.sqrt(Math.pow(latDist, 2) + Math.pow(lngDist, 2));
        if (minDist < prevDist) {
          // console.log("continuous point: min dist");
          lat = element[0];
          lng = element[1];
        }
      }
    }
  });
  return [lat, lng]
}


function getSideWalkClassificationColor(features): string {
  // if (features.includes(Detached_Sidewalk)) {
  //   return sidewalkColorMap[Detached_Sidewalk];
  // } else if (features.includes(Sidewalk)) {
  //   return sidewalkColorMap[Sidewalk];
  // }
  // //no sidewalk
  // return sidewalkColorMap[No_Sidewalk];
  if (features.includes(Detached_Sidewalk)) {
    return sidewalkColorMap[Detached_Sidewalk];
  } else if (features.includes(No_Sidewalk)) {
    return sidewalkColorMap[No_Sidewalk];
  }else{
    return sidewalkColorMap[Sidewalk];
  }
}

function resetPolyLines() {
  if (allSideWalkPaths != null && Object.keys(allSideWalkPaths).length > 0) {
    // console.log("inside");
    Object.keys(allSideWalkPaths).forEach(element => {
      allSideWalkPaths[element].forEach(e => {
        e.setMap(null);
      });
    });
  }
}

/* For each lat-long, draws lines of length (granualrityPath) based on direction */
function drawOnMap(allPaths): any {
  resetPolyLines();
  let allSideWalkPathsArr = {} as any;
  // console.log(allPaths); 
  let baseCoords: Array<Array<number>> = []
  allPaths.forEach(element => {
    baseCoords.push([element.latitude, element.longitude]);
  });
  // console.log(baseCoords);
  allPaths.forEach(element => {
    let path = [] as any;
    // console.log(element);
    // let mapDirection = parseFloat(element['direction'])
    // let radianDir = (mapDirection * 3.14159265358979311600) / 180.0
    // console.log(radianDir);
    // console.log(mapDirection);
    // let lat_to: number = element.latitude + (granualrityPath * Math.cos(radianDir));
    // let lng_to: number = element.longitude + (granualrityPath * Math.sin(radianDir));
    // [lat_to, lng_to] = checkForContiguousPoint([lat_to, lng_to], baseCoords);
    let lat_from = element.lat1;
    let lng_from = element.lng1;
    let lat_to = element.lat2;
    let lng_to = element.lng2;
    // if(element["PlaceID"]=="27" || true){
    console.log("placeID: " + element["PlaceID"] + " from: " + lat_from + " " + lng_from + " - to:  " + lat_to + " " + lng_to);
    // }
    path.push({
      lat: parseFloat(lat_from),
      lng: parseFloat(lng_from)
    });
    path.push({
      lat: parseFloat(lat_to),
      lng: parseFloat(lng_to)
    });
    let color = getSideWalkClassificationColor(element.label);
    let strokeObject = new google.maps.Polyline({
      path: path,
      map: map,
      clickable: false,
      strokeColor: color,
      strokeOpacity: 1.0,
      strokeWeight: 10
    });

    if (color in allSideWalkPathsArr) {
      allSideWalkPathsArr[color].push(strokeObject);
    } else {
      allSideWalkPathsArr[color] = [strokeObject];
    }
  });

  return allSideWalkPathsArr;
}

function drawSidewalkData(mapBounds): any {
  let lats: any = [];
  let lngs: any = [];
  var ne: any = mapBounds.getNorthEast();
  var sw: any = mapBounds.getSouthWest();
  lats.push(ne.lat());
  lats.push(sw.lat());
  lngs.push(ne.lng());
  lngs.push(sw.lng());
  var xhttp = new XMLHttpRequest();
  xhttp.onreadystatechange = function () {
    if (this.readyState == 4 && this.status == 200) {
      var data = JSON.parse(this.responseText);
      allSideWalkPaths = drawOnMap(data);
    }
  };
  let url_api = "https://ohemg90am4.execute-api.us-east-1.amazonaws.com/test/query-eagleview-dynamo-api?lat_min=" + Math.min(...lats) + "&lat_max=" + Math.max(...lats) + "&lon_min=" + Math.min(...lngs) + "&lon_max=" + Math.max(...lngs);
  console.log(url_api);
  xhttp.open("GET", url_api, false);
  xhttp.send();
}

function initMap() {
  let url_string = window.location.href;
  var url = new URL(url_string);
  var LAT = Number(url.searchParams.get("lat"));
  var LNG = Number(url.searchParams.get("lng"));
  if(!LAT){
    LAT=41.8779405787;
  }
  if(!LNG){
    LNG=-71.4099990117;
  }
  // sets up the google maps div with the provided options
  map = new google.maps.Map(document.getElementById("map"), {
    // center: { lat: 33.291537, lng: -111.859904 },
    // center: { lat: 33.450315, lng: -112.08115054247171 },
    center: { lat: LAT, lng: LNG },
    zoom: 19,
    mapTypeId: 'satellite',
  });

  // console.log("here everytime?");
  // creating a container div for holding the checkboxes
  const container = document.createElement("div");
  container.className = "container";

  const form = document.createElement("ul");
  form.className = "ks-cboxtags";

  // appending the three checkboxes to the container
  form.appendChild(CreateBox(Sidewalk));
  form.appendChild(CreateBox(Detached_Sidewalk));
  form.appendChild(CreateBox(No_Sidewalk));

  container.appendChild(form);

  const legend: any = document.createElement("div");
  legend.innerHTML = "<h3>Color Mappings</h3><hr><br>";
  legend.style.background = "#fff";
  legend.style.padding = "10px";
  legend.style.border = "3px solid #000";
  legend.style.margin = "10px";
  legend.id = "legend";

  for (const key in sidewalkColorMap) {
    console.log(key);
    const type = sidewalkColorMap[key];
    const name = type.name;
    let br = document.createElement("br");
    let div = document.createElement("div");
    div.style.float = "left";
    div.style.margin = "5px";
    div.innerHTML = "<div style='width: 20px;height: 20px;margin-right:5px;float: left;background: " + sidewalkColorMap[key] + ";'></div><b>" + key + "</b>";
    console.log(div);
    legend.appendChild(div);
    legend.appendChild(br);
  }

  map.controls[google.maps.ControlPosition.TOP_CENTER].push(container);
  map.controls[google.maps.ControlPosition.RIGHT_BOTTOM].push(legend);

  google.maps.event.addListener(map, 'idle', () => {
    clearTimeout(changetm)
    changetm = setTimeout(() => {
      drawSidewalkData(map.getBounds())
      // console.log(document.getElementById(Sidewalk))
      // console.log(document.querySelectorAll("input"))
      var detached_sidewalk_input: HTMLInputElement = <HTMLInputElement>document.getElementById(Detached_Sidewalk)
      toggleLines(Detached_Sidewalk, detached_sidewalk_input.checked)
      var sidewalk_input: HTMLInputElement = <HTMLInputElement>document.getElementById(Sidewalk)
      toggleLines(Sidewalk, sidewalk_input.checked)
      var no_sidewalk_input: HTMLInputElement = <HTMLInputElement>document.getElementById(No_Sidewalk)
      toggleLines(No_Sidewalk, no_sidewalk_input.checked)
    }, 3000);
  });


}

loader
  .load()
  .then(() => {
    initMap();
  })
  .catch(e => {
  });

export { loader };

import "./style.css";