const now = new Date();

function isoHoursAgo(hoursAgo) {
  return new Date(now.getTime() - hoursAgo * 60 * 60 * 1000).toISOString();
}

function makeIncident(overrides) {
  return {
    incident_no: overrides.incident_no,
    timestamp: overrides.timestamp,
    description: overrides.description,
    location: overrides.location,
    neighborhood: overrides.neighborhood || "",
    map_filename: overrides.map_filename || "fixture-map.svg",
    likes: overrides.likes ?? 0,
    comments: overrides.comments ?? [],
    type: overrides.type || "Traffic Hazard",
    active: overrides.active ?? false,
    source: overrides.source || "CHP",
    severity: overrides.severity ?? null,
    Details: overrides.Details || [],
    latitude: overrides.latitude ?? 32.7157,
    longitude: overrides.longitude ?? -117.1611,
  };
}

const baseIncidents = [
  makeIncident({
    incident_no: "A-1001",
    timestamp: isoHoursAgo(0.2),
    description: "SIG Alert blocking two lanes near I-5 downtown.",
    location: "Downtown",
    neighborhood: "I-5 NB at SR-94",
    likes: 42,
    comments: [
      {
        username: "CoastalCommuter",
        comment: "Traffic is backing up past the 163 split.",
        timestamp: isoHoursAgo(0.15),
      },
      {
        username: "SDRoadWatch",
        comment: "Use 805 north if you can.",
        timestamp: isoHoursAgo(0.1),
      },
    ],
    type: "SIG Alert",
    active: true,
    source: "CHP",
    severity: 5,
    Details: ["Two northbound lanes blocked", "Tow and Caltrans en route"],
    latitude: 32.7169,
    longitude: -117.1538,
  }),
  makeIncident({
    incident_no: "A-1002",
    timestamp: isoHoursAgo(0.8),
    description: "Traffic accident with injuries near North Park.",
    location: "North Park",
    neighborhood: "University Ave at 30th St",
    likes: 18,
    comments: [
      {
        username: "HarborFox",
        comment: "Heavy slowdown here.",
        timestamp: isoHoursAgo(0.7),
      },
    ],
    type: "TRAFFIC ACCIDENT",
    active: true,
    source: "SDFD",
    severity: 4,
    Details: ["Medic requested", "One lane open"],
    latitude: 32.7487,
    longitude: -117.1305,
  }),
  makeIncident({
    incident_no: "A-1003",
    timestamp: isoHoursAgo(1.5),
    description: "Overturned vehicle blocking the I-8 west connector in Mission Valley.",
    location: "Mission Valley",
    neighborhood: "I-8 WB at SR-163",
    likes: 27,
    comments: [
      {
        username: "MesaDriver",
        comment: "Connector is fully stopped.",
        timestamp: isoHoursAgo(1.3),
      },
    ],
    type: "Road Closure",
    active: true,
    source: "CHP",
    severity: 4,
    Details: ["Vehicle on its side", "Heavy-duty tow requested"],
    latitude: 32.7696,
    longitude: -117.1532,
  }),
  makeIncident({
    incident_no: "A-1004",
    timestamp: isoHoursAgo(2.2),
    description: "Vegetation fire producing smoke near SR-52 and Mast Boulevard.",
    location: "Santee",
    neighborhood: "Mast Blvd at SR-52",
    likes: 31,
    comments: [],
    type: "VEGETATION FIRE",
    active: true,
    source: "SDFD",
    severity: 4,
    Details: ["Forward spread stopped", "Crews checking hot spots"],
    latitude: 32.8395,
    longitude: -116.9841,
  }),
  makeIncident({
    incident_no: "A-1005",
    timestamp: isoHoursAgo(3.5),
    description: "Police activity has closed Harbor Drive near the Convention Center.",
    location: "Downtown",
    neighborhood: "Harbor Dr at 5th Ave",
    likes: 22,
    comments: [],
    type: "POLICE ACTIVITY",
    active: true,
    source: "SDPD",
    severity: 3,
    Details: ["Use Pacific Highway", "Pedestrian access remains open"],
    latitude: 32.7069,
    longitude: -117.1626,
  }),
  makeIncident({
    incident_no: "A-1006",
    timestamp: isoHoursAgo(4),
    description: "Stalled box truck blocking the right lane on I-805 north.",
    location: "Kearny Mesa",
    neighborhood: "I-805 NB at Balboa Ave",
    likes: 11,
    comments: [],
    type: "Traffic Hazard",
    active: true,
    source: "CHP",
    severity: 2,
    Details: ["No injuries reported", "Freeway service patrol assigned"],
    latitude: 32.8218,
    longitude: -117.1397,
  }),
  makeIncident({
    incident_no: "A-1007",
    timestamp: isoHoursAgo(5.2),
    description: "Cliff rescue underway above Black's Beach; emergency vehicles in the area.",
    location: "La Jolla",
    neighborhood: "Torrey Pines Scenic Dr",
    likes: 36,
    comments: [],
    type: "RESCUE",
    active: true,
    source: "SDSO",
    severity: 4,
    Details: ["Technical rescue team deployed", "Avoid beach access road"],
    latitude: 32.8892,
    longitude: -117.2528,
  }),
  makeIncident({
    incident_no: "A-1008",
    timestamp: isoHoursAgo(6.5),
    description: "Multi-vehicle crash slowing southbound I-5 near Oceanside Boulevard.",
    location: "Oceanside",
    neighborhood: "I-5 SB at Oceanside Blvd",
    likes: 29,
    comments: [],
    type: "TRAFFIC ACCIDENT",
    active: true,
    source: "CHP",
    severity: 3,
    Details: ["Three vehicles involved", "Shoulder and lane four blocked"],
    latitude: 33.1884,
    longitude: -117.3683,
  }),
  makeIncident({
    incident_no: "A-1009",
    timestamp: isoHoursAgo(8),
    description: "Earlier collision cleared from Telegraph Canyon Road after a brief closure.",
    location: "Chula Vista",
    neighborhood: "Telegraph Canyon Rd",
    likes: 9,
    type: "TRAFFIC ACCIDENT",
    active: false,
    source: "SDPD",
    severity: 3,
    latitude: 32.6288,
    longitude: -117.0381,
  }),
  makeIncident({
    incident_no: "A-1010",
    timestamp: isoHoursAgo(10),
    description: "Medical response completed after a cyclist collision on Mira Mesa Boulevard.",
    location: "Mira Mesa",
    neighborhood: "Mira Mesa Blvd at Camino Ruiz",
    likes: 14,
    type: "MEDICAL",
    active: false,
    source: "SDFD",
    severity: 3,
    latitude: 32.9153,
    longitude: -117.1437,
  }),
  makeIncident({
    incident_no: "A-1011",
    timestamp: isoHoursAgo(12),
    description: "Police cleared an earlier intersection closure near Balboa Avenue.",
    location: "Clairemont",
    neighborhood: "Balboa Ave at Genesee Ave",
    likes: 7,
    type: "POLICE ACTIVITY",
    active: false,
    source: "SDPD",
    severity: 2,
    latitude: 32.8079,
    longitude: -117.1819,
  }),
  makeIncident({
    incident_no: "A-1012",
    timestamp: isoHoursAgo(14),
    description: "Coast Highway reopened after utility crews removed a fallen pole.",
    location: "Encinitas",
    neighborhood: "Coast Hwy 101 at D St",
    likes: 13,
    type: "Road Closure",
    active: false,
    source: "CHP",
    severity: 2,
    latitude: 33.0477,
    longitude: -117.2946,
  }),
  makeIncident({
    incident_no: "A-1013",
    timestamp: isoHoursAgo(16),
    description: "Two-car collision cleared from Main Street near the El Cajon Transit Center.",
    location: "El Cajon",
    neighborhood: "Main St at Marshall Ave",
    likes: 6,
    type: "TRAFFIC ACCIDENT",
    active: false,
    source: "SDSO",
    severity: 2,
    latitude: 32.7948,
    longitude: -116.9754,
  }),
  makeIncident({
    incident_no: "A-1014",
    timestamp: isoHoursAgo(18),
    description: "Small brush fire extinguished near the Espola Road trailhead.",
    location: "Poway",
    neighborhood: "Espola Rd at Lake Poway Rd",
    likes: 17,
    type: "VEGETATION FIRE",
    active: false,
    source: "SDFD",
    severity: 3,
    latitude: 33.0054,
    longitude: -117.0112,
  }),
  makeIncident({
    incident_no: "A-1015",
    timestamp: isoHoursAgo(20),
    description: "Police activity cleared from Broadway after a short traffic hold.",
    location: "Downtown",
    neighborhood: "Broadway at 10th Ave",
    likes: 8,
    type: "POLICE ACTIVITY",
    active: false,
    source: "SDPD",
    severity: 2,
    latitude: 32.7153,
    longitude: -117.1551,
  }),
  makeIncident({
    incident_no: "A-1016",
    timestamp: isoHoursAgo(22),
    description: "Single-vehicle spinout cleared from I-805 near Plaza Boulevard.",
    location: "National City",
    neighborhood: "I-805 at Plaza Blvd",
    likes: 5,
    type: "SPINOUT",
    active: false,
    source: "CHP",
    severity: 2,
    latitude: 32.6768,
    longitude: -117.0883,
  }),
  makeIncident({
    incident_no: "A-1017",
    timestamp: isoHoursAgo(26),
    description: "Tree branches removed from eastbound I-8 after overnight winds.",
    location: "Lakeside",
    neighborhood: "I-8 EB at Lake Jennings Park Rd",
    likes: 4,
    type: "Traffic Hazard",
    active: false,
    source: "CHP",
    severity: 2,
    latitude: 32.8384,
    longitude: -116.8807,
  }),
  makeIncident({
    incident_no: "A-1018",
    timestamp: isoHoursAgo(36),
    description: "Overnight paving work completed on Camino Del Mar.",
    location: "Del Mar",
    neighborhood: "Camino Del Mar at 15th St",
    likes: 3,
    type: "Construction",
    active: false,
    source: "CHP",
    severity: 1,
    latitude: 32.9595,
    longitude: -117.2653,
  }),
  makeIncident({
    incident_no: "A-1019",
    timestamp: isoHoursAgo(7.2),
    description: "Disabled sedan removed from SR-78 west near Twin Oaks Valley Road.",
    location: "San Marcos",
    neighborhood: "SR-78 WB at Twin Oaks Valley Rd",
    likes: 5,
    type: "Traffic Hazard",
    active: false,
    source: "CHP",
    severity: 1,
    latitude: 33.1378,
    longitude: -117.1816,
  }),
  makeIncident({
    incident_no: "A-1020",
    timestamp: isoHoursAgo(9.1),
    description: "Fire crews cleared a vehicle fire from the I-15 shoulder.",
    location: "Rancho Bernardo",
    neighborhood: "I-15 SB at Camino Del Norte",
    likes: 12,
    type: "VEHICLE FIRE",
    active: false,
    source: "SDFD",
    severity: 3,
    latitude: 33.0174,
    longitude: -117.1076,
  }),
  makeIncident({
    incident_no: "A-1021",
    timestamp: isoHoursAgo(11.3),
    description: "Minor collision cleared from Mission Gorge Road near Zion Avenue.",
    location: "Mission Valley",
    neighborhood: "Mission Gorge Rd at Zion Ave",
    likes: 6,
    type: "TRAFFIC ACCIDENT",
    active: false,
    source: "SDPD",
    severity: 2,
    latitude: 32.8044,
    longitude: -117.0844,
  }),
  makeIncident({
    incident_no: "A-1022",
    timestamp: isoHoursAgo(13.4),
    description: "Deputies reopened Valley Center Road after an earlier investigation.",
    location: "Valley Center",
    neighborhood: "Valley Center Rd at Cole Grade Rd",
    likes: 10,
    type: "POLICE ACTIVITY",
    active: false,
    source: "SDSO",
    severity: 2,
    latitude: 33.2184,
    longitude: -117.0342,
  }),
  makeIncident({
    incident_no: "A-1023",
    timestamp: isoHoursAgo(17.2),
    description: "Water-main repair completed and lanes reopened on Friars Road.",
    location: "Mission Valley",
    neighborhood: "Friars Rd at Qualcomm Way",
    likes: 15,
    type: "Road Closure",
    active: false,
    source: "SDPD",
    severity: 2,
    latitude: 32.7833,
    longitude: -117.1225,
  }),
  makeIncident({
    incident_no: "A-1024",
    timestamp: isoHoursAgo(21.2),
    description: "Earlier pedestrian collision cleared from Girard Avenue.",
    location: "La Jolla",
    neighborhood: "Girard Ave at Pearl St",
    likes: 9,
    type: "TRAFFIC ACCIDENT",
    active: false,
    source: "SDPD",
    severity: 3,
    latitude: 32.8397,
    longitude: -117.2741,
  }),
];

function compareIncidentsDescending(a, b) {
  const ts = new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  if (ts !== 0) return ts;
  return b.incident_no.localeCompare(a.incident_no);
}

function buildHourlyData(incidents, referenceTime = now) {
  const buckets = Array.from({ length: 24 }, () => 0);
  const start = referenceTime.getTime() - 24 * 60 * 60 * 1000;
  for (const incident of incidents) {
    const bucket = Math.floor((new Date(incident.timestamp).getTime() - start) / (60 * 60 * 1000));
    if (bucket >= 0 && bucket < 24) {
      buckets[bucket] += 1;
    }
  }
  return buckets;
}

function buildPreviousWeekHourlyData(incidents) {
  const end = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const start = new Date(end.getTime() - 24 * 60 * 60 * 1000);
  const firstDay = new Date(start).setHours(0, 0, 0, 0);
  const lastDay = new Date(end.getTime() - 1).setHours(0, 0, 0, 0);
  for (let day = new Date(firstDay); day.getTime() <= lastDay; day.setDate(day.getDate() + 1)) {
    if (!incidents.some(incident => new Date(incident.timestamp).toDateString() === day.toDateString())) {
      return null;
    }
  }
  return buildHourlyData(incidents, end);
}

function buildDayData(incidents, days) {
  const buckets = Array.from({ length: days }, () => 0);
  for (const incident of incidents) {
    const ageDays = Math.floor((now.getTime() - new Date(incident.timestamp).getTime()) / (24 * 60 * 60 * 1000));
    if (ageDays >= 0 && ageDays < days) {
      buckets[days - 1 - ageDays] += 1;
    }
  }
  return buckets;
}

function buildMonthData(incidents) {
  return buildDayData(incidents, 30);
}

function buildYearData(incidents) {
  const buckets = Array.from({ length: 12 }, () => 0);
  for (const incident of incidents) {
    const incidentDate = new Date(incident.timestamp);
    const monthDelta =
      now.getMonth() -
      incidentDate.getMonth() +
      (now.getFullYear() - incidentDate.getFullYear()) * 12;
    if (monthDelta >= 0 && monthDelta < 12) {
      buckets[11 - monthDelta] += 1;
    }
  }
  return buckets;
}

function filterByDate(incidents, dateFilter) {
  if (dateFilter === "week") {
    return incidents.filter((incident) => new Date(incident.timestamp).getTime() >= now.getTime() - 7 * 24 * 60 * 60 * 1000);
  }
  if (dateFilter === "month") {
    return incidents.filter((incident) => new Date(incident.timestamp).getTime() >= now.getTime() - 30 * 24 * 60 * 60 * 1000);
  }
  if (dateFilter === "year") {
    return incidents.filter((incident) => new Date(incident.timestamp).getTime() >= now.getTime() - 365 * 24 * 60 * 60 * 1000);
  }
  return incidents.filter((incident) => new Date(incident.timestamp).getTime() >= now.getTime() - 24 * 60 * 60 * 1000);
}

export function cloneIncident(incident) {
  return JSON.parse(JSON.stringify(incident));
}

export function seedIncidents() {
  return baseIncidents
    .map(cloneIncident)
    .sort(compareIncidentsDescending);
}

export function filterIncidents(incidents, query) {
  const limit = Number(query.get("limit") || "20");
  const cursor = query.get("cursor");
  const types = query.getAll("type");
  const locations = query.getAll("location");
  const sources = query.getAll("source");
  const activeOnly = query.get("active_only") === "true";

  let filtered = [...incidents];

  if (types.length > 0) {
    filtered = filtered.filter((incident) => types.includes(incident.type));
  }
  if (locations.length > 0) {
    filtered = filtered.filter((incident) => locations.includes(incident.location));
  }
  if (sources.length > 0) {
    filtered = filtered.filter((incident) => sources.includes(incident.source));
  }
  if (activeOnly) {
    filtered = filtered.filter((incident) => incident.active);
  }

  filtered.sort(compareIncidentsDescending);

  if (cursor) {
    const [cursorTimestamp, cursorIncidentNo] = cursor.split("|");
    filtered = filtered.filter((incident) => {
      if (incident.timestamp < cursorTimestamp) {
        return true;
      }
      if (incident.timestamp > cursorTimestamp) {
        return false;
      }
      return incident.incident_no < cursorIncidentNo;
    });
  }

  return filtered.slice(0, limit).map(cloneIncident);
}

export function buildStats(incidents, query) {
  const sources = query.getAll("source");
  const dateFilter = query.get("date_filter") || "day";

  let filtered = [...incidents];
  if (sources.length > 0) {
    filtered = filtered.filter((incident) => sources.includes(incident.source));
  }

  const dateScoped = filterByDate(filtered, dateFilter);
  const todayScoped = filterByDate(filtered, "day");
  const lastHourThreshold = now.getTime() - 60 * 60 * 1000;
  const eventsLastHour = filtered.filter(
    (incident) => new Date(incident.timestamp).getTime() >= lastHourThreshold,
  ).length;

  const incidentsByType = {};
  const topLocations = {};
  for (const incident of dateScoped) {
    incidentsByType[incident.type] = (incidentsByType[incident.type] || 0) + 1;
    if (incident.location) {
      topLocations[incident.location] = (topLocations[incident.location] || 0) + 1;
    }
  }

  let hourlyData;
  if (dateFilter === "year") {
    hourlyData = buildYearData(filtered);
  } else if (dateFilter === "month") {
    hourlyData = buildMonthData(filtered);
  } else if (dateFilter === "week") {
    hourlyData = buildDayData(filtered, 7);
  } else {
    hourlyData = buildHourlyData(filtered);
  }

  return {
    eventsToday: todayScoped.length,
    eventsLastHour,
    eventsActive: filtered.filter((incident) => incident.active).length,
    totalIncidents: dateScoped.length,
    incidentsByType,
    topLocations,
    hourlyData,
    previousWeekHourlyData: dateFilter === "day" ? buildPreviousWeekHourlyData(filtered) : null,
    historicalCurrentHourAverage: 2,
    historicalHourSampleCount: 6,
    generatedAt: new Date().toISOString(),
  };
}
