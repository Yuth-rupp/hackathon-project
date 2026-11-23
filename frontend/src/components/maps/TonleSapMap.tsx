"use client";

import React, { useEffect, useRef, useState } from "react";
import { MONITORING_LOCATIONS, TONLE_SAP_CENTER } from "@/lib/constants";
import { Station, RiskAssessment, MonitoringLocation } from "@/types";
import {
  Layers,
  MapPin,
  Waves,
  ShieldAlert,
  ShieldCheck,
  Maximize2,
  RefreshCw,
} from "lucide-react";

export interface SatelliteFootprint {
  id: string;
  name?: string;
  satellite?: string;
  coordinates?: [number, number][]; // [lat, lon][]
  bbox?: [number, number, number, number]; // [minLon, minLat, maxLon, maxLat]
}

export interface TonleSapMapProps {
  selectedStationId?: string;
  selectedLocationId?: string;
  onSelectStation?: (station: Station | any) => void;
  onSelectLocation?: (location: MonitoringLocation) => void;
  stations?: Station[];
  riskAssessments?: RiskAssessment[];
  footprints?: SatelliteFootprint[];
  showJRCWater?: boolean;
  className?: string;
  height?: string;
}

// High-priority Tonle Sap agricultural, floating community & lowland floodplain hubs
const COMMUNITY_RISK_HUBS = [
  // Kampong Chhnang
  {
    id: "chhnok-tru",
    provinceId: "kampong-chhnang",
    name: "Chhnok Tru Floating Commune",
    name_km: "ឃុំឆ្នុកទ្រូ (ភូមិបណ្តែតទឹក)",
    province: "Kampong Chhnang",
    lat: 12.5089,
    lon: 104.4512,
    fallback_risk: "very_high",
    livelihood: "Floating Fishing & Cage Aquaculture",
    advisory:
      "Secure floating houses & fish cages; relocate vulnerable families to Phnom Kong Rei Safe Mound.",
  },
  {
    id: "boribo-rice",
    provinceId: "kampong-chhnang",
    name: "Boribo Lowland Rice Plain",
    name_km: "វាលស្រែទំនាបស្រុកបរិបូណ៌",
    province: "Kampong Chhnang",
    lat: 12.3542,
    lon: 104.4785,
    fallback_risk: "high",
    livelihood: "Recession & Deepwater Rice Farming",
    advisory:
      "Harvest mature dry-season paddy early; move livestock to Wat Boribo Elevated Mound.",
  },
  {
    id: "kampong-tralac",
    provinceId: "kampong-chhnang",
    name: "Kampong Tralach Floodplain",
    name_km: "វាលទំនាបកំពង់ត្រឡាច",
    province: "Kampong Chhnang",
    lat: 11.9085,
    lon: 104.7614,
    fallback_risk: "high",
    livelihood: "Irrigated Rice & Vegetable Polders",
    advisory: "Check embankment sluice gates near Prek Kdam bottleneck.",
  },
  // Pursat
  {
    id: "kampong-luong-village",
    provinceId: "pursat",
    name: "Kampong Luong Floating Village",
    name_km: "ភូមិបណ្តែតទឹកកំពង់ហ្លួង",
    province: "Pursat",
    lat: 12.5736,
    lon: 104.2118,
    fallback_risk: "high",
    livelihood: "Floating Community & Boat Transport",
    advisory:
      "High wave & backwater swell advisory; moor boats along Krakor Safe Highland.",
  },
  {
    id: "bakan-rice-bowl",
    provinceId: "pursat",
    name: "Bakan Agricultural Rice Bowl",
    name_km: "តំបន់កសិកម្មស្រូវស្រុកបាកាន",
    province: "Pursat",
    lat: 12.6415,
    lon: 103.7924,
    fallback_risk: "moderate",
    livelihood: "Wet-Season Paddy & Seedbeds",
    advisory:
      "Flash runoff from Cardamom foothills; clear field drainage canals.",
  },
  {
    id: "kandieng-floodplain",
    provinceId: "pursat",
    name: "Kandieng Riverine Farms",
    name_km: "កសិដ្ឋានតាមដងស្ទឹងកណ្តៀង",
    province: "Pursat",
    lat: 12.5612,
    lon: 103.9845,
    fallback_risk: "moderate",
    livelihood: "Alluvial Cropland & Orchards",
    advisory: "Monitor Pursat River stage rise over next 48 hours.",
  },
  // Battambang
  {
    id: "ek-phnom-preak-toal",
    provinceId: "battambang",
    name: "Prek Toal & Ek Phnom Wetland",
    name_km: "ព្រែកទាល់ និងតំបន់ដីសើមឯកភ្នំ",
    province: "Battambang",
    lat: 13.2356,
    lon: 103.6589,
    fallback_risk: "high",
    livelihood: "Floating Villages & Biosphere Fisheries",
    advisory:
      "Rising lake expansion submerging low stilts; prepare elevated storage.",
  },
  {
    id: "sangke-rice-belt",
    provinceId: "battambang",
    name: "Sangke River Rice Belt",
    name_km: "ខ្សែក្រវាត់ស្រូវដងស្ទឹងសង្កែ",
    province: "Battambang",
    lat: 13.0642,
    lon: 103.2841,
    fallback_risk: "moderate",
    livelihood: "Commercial Jasmine Rice Production",
    advisory:
      "Moderate river inflow; protect stored grain silos from ground moisture.",
  },
  {
    id: "moung-ruessei",
    provinceId: "battambang",
    name: "Moung Ruessei Lowland Farms",
    name_km: "វាលស្រែទំនាបមោងឫស្សី",
    province: "Battambang",
    lat: 12.7745,
    lon: 103.4512,
    fallback_risk: "low",
    livelihood: "Rainfed Rice & Cassava",
    advisory:
      "Normal soil moisture; favorable conditions for field operations.",
  },
  // Siem Reap
  {
    id: "kampong-phluk",
    provinceId: "siem-reap",
    name: "Kampong Phluk Stilted Village",
    name_km: "ភូមិកំពង់ភ្លុក",
    province: "Siem Reap",
    lat: 13.2045,
    lon: 103.9742,
    fallback_risk: "moderate",
    livelihood: "Stilted Fishing & Eco-Tourism Village",
    advisory:
      "Seasonal water rise within normal stilts clearance; evacuate livestock to Roluos Safe Mound if >9.2m.",
  },
  {
    id: "chong-kneas",
    provinceId: "siem-reap",
    name: "Chong Kneas Lakeside Port",
    name_km: "កំពង់ផែចុងឃ្នៀស",
    province: "Siem Reap",
    lat: 13.2812,
    lon: 103.8246,
    fallback_risk: "moderate",
    livelihood: "Lakeside Community & Ferry Hub",
    advisory: "Adjust floating pier moorings for +0.45m lake level anomaly.",
  },
  {
    id: "puok-paddy-zone",
    provinceId: "siem-reap",
    name: "Puok West Agricultural Zone",
    name_km: "តំបន់កសិកម្មស្រុកពួក",
    province: "Siem Reap",
    lat: 13.4385,
    lon: 103.7291,
    fallback_risk: "low",
    livelihood: "Wet-Season Rice & Livestock",
    advisory: "Low flood probability; standard irrigation schedule.",
  },
  // Kampong Thom
  {
    id: "stung-sen-delta",
    provinceId: "kampong-thom",
    name: "Stung Sen Floodplain & Rice Fields",
    name_km: "វាលទំនាបស្ទឹងសែន កំពង់ធំ",
    province: "Kampong Thom",
    lat: 12.6845,
    lon: 104.8612,
    fallback_risk: "high",
    livelihood: "Deepwater Rice & Riverbank Farms",
    advisory:
      "Stung Sen gauge nearing alarm threshold (12.82m); move cattle to Tuol Prasat Safe Mound.",
  },
  {
    id: "kampong-svay-polders",
    provinceId: "kampong-thom",
    name: "Kampong Svay Flood Recession Polders",
    name_km: "តំបន់ស្រែប្រាំងកំពង់ស្វាយ",
    province: "Kampong Thom",
    lat: 12.7618,
    lon: 104.6425,
    fallback_risk: "moderate",
    livelihood: "Recession Paddy & Aquaculture",
    advisory:
      "Backwater expansion entering outer canals; reinforce bund walls.",
  },
];

// Designated Safe Elevated Mounds (Tuol Sopheakpheap / ទួលសុវត្ថិភាព) across the 5 riparian provinces
const SAFE_ELEVATED_MOUNDS = [
  {
    id: "mound-phnom-kong-rei",
    name: "Tuol Sopheakpheap Phnom Kong Rei",
    name_km: "ទួលសុវត្ថិភាពភ្នំកង្រី",
    province: "Kampong Chhnang",
    lat: 12.2685,
    lon: 104.6892,
    elevation_m: 18.5,
    capacity: "450 Households / 1,200 Livestock",
    facilities: "Clean water well, solar lighting, medical post & boat landing",
  },
  {
    id: "mound-wat-boribo",
    name: "Tuol Wat Boribo High Pagoda Ground",
    name_km: "ទួលសុវត្ថិភាពវត្តបរិបូណ៌",
    province: "Kampong Chhnang",
    lat: 12.3124,
    lon: 104.4518,
    elevation_m: 15.2,
    capacity: "320 Households / 800 Livestock",
    facilities: "Elevated pagoda hall, grain storage & NCDM relief depot",
  },
  {
    id: "mound-krakor-highland",
    name: "Tuol Sopheakpheap Krakor Highland",
    name_km: "ទួលសុវត្ថិភាពស្រុកក្រគរ",
    province: "Pursat",
    lat: 12.5218,
    lon: 104.1845,
    elevation_m: 16.8,
    capacity: "500 Households / 1,500 Livestock",
    facilities: "All-weather road access, water tanks & veterinary shelter",
  },
  {
    id: "mound-bakan-sanctuary",
    name: "Tuol Sopheakpheap Bakan Safe Zone",
    name_km: "ទួលសុវត្ថិភាពស្រុកបាកាន",
    province: "Pursat",
    lat: 12.6682,
    lon: 103.8145,
    elevation_m: 17.4,
    capacity: "380 Households / 950 Livestock",
    facilities: "Community school shelter, emergency rice reserve & sanitation",
  },
  {
    id: "mound-ek-phnom-pagoda",
    name: "Tuol Wat Ek Phnom Elevated Shelter",
    name_km: "ទួលសុវត្ថិភាពវត្តឯកភ្នំ",
    province: "Battambang",
    lat: 13.1584,
    lon: 103.2412,
    elevation_m: 16.0,
    capacity: "420 Households / 1,100 Livestock",
    facilities: "Boat mooring pier, clean water filtration & first-aid station",
  },
  {
    id: "mound-roluos-highland",
    name: "Tuol Sopheakpheap Roluos Safe Mound",
    name_km: "ទួលសុវត្ថិភាពរលួស",
    province: "Siem Reap",
    lat: 13.3142,
    lon: 103.9815,
    elevation_m: 17.9,
    capacity: "400 Households / 1,000 Livestock",
    facilities: "Direct National Road 6 access, solar power & livestock pen",
  },
  {
    id: "mound-stung-sen-tuol",
    name: "Tuol Prasat Stung Sen Safe Mound",
    name_km: "ទួលសុវត្ថិភាពប្រាសាទស្ទឹងសែន",
    province: "Kampong Thom",
    lat: 12.7348,
    lon: 104.9012,
    elevation_m: 16.5,
    capacity: "360 Households / 900 Livestock",
    facilities: "Elevated community hall, potable water & seed-bank storage",
  },
];

export function TonleSapMap({
  selectedStationId,
  selectedLocationId,
  onSelectStation,
  onSelectLocation,
  stations = [],
  riskAssessments = [],
  footprints = [],
  showJRCWater = true,
  className = "",
  height = "540px",
}: TonleSapMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const baseLayerGroupRef = useRef<any>(null);
  const layerGroupsRef = useRef<{
    stations?: any;
    locations?: any;
    safeMounds?: any;
    provinces?: any;
    jrc?: any;
    footprints?: any;
  }>({});

  const [activeBaseLayer, setActiveBaseLayer] = useState<
    "dark" | "osm" | "satellite"
  >("dark");
  const [jrcVisible, setJrcVisible] = useState(showJRCWater);
  const [provincesVisible, setProvincesVisible] = useState(true);
  const [stationsVisible, setStationsVisible] = useState(true);
  const [riskMarkersVisible, setRiskMarkersVisible] = useState(true);
  const [safeMoundsVisible, setSafeMoundsVisible] = useState(true);
  const [isLoaded, setIsLoaded] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);

  // Initialize Leaflet Map
  useEffect(() => {
    let isCancelled = false;

    async function initMap() {
      if (typeof window === "undefined" || !mapContainerRef.current) return;
      if (mapInstanceRef.current) return;

      const L = (await import("leaflet")).default;

      if (isCancelled || !mapContainerRef.current) return;

      const darkBase = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        {
          attribution: "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ",
          maxZoom: 16,
        },
      );

      const darkLabels = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
        {
          attribution: "Tiles &copy; Esri",
          maxZoom: 16,
        },
      );

      const baseGroup = L.layerGroup([darkBase, darkLabels]);

      const jrcWaterLayer = L.tileLayer(
        "https://storage.googleapis.com/global-surface-water/tiles2021/occurrence/{z}/{x}/{y}.png",
        {
          opacity: 0.75,
          attribution: "EC JRC / Google Earth Engine (Global Surface Water)",
          maxZoom: 14,
        },
      );

      const map = L.map(mapContainerRef.current, {
        center: TONLE_SAP_CENTER,
        zoom: 8,
        minZoom: 6,
        maxZoom: 16,
        layers: [baseGroup],
        zoomControl: false,
      });

      L.control.zoom({ position: "topright" }).addTo(map);

      mapInstanceRef.current = map;
      baseLayerGroupRef.current = baseGroup;
      layerGroupsRef.current.jrc = jrcWaterLayer;

      if (jrcVisible) {
        jrcWaterLayer.addTo(map);
      }

      const provincesGroup = L.layerGroup().addTo(map);
      const stationsGroup = L.layerGroup().addTo(map);
      const locationsGroup = L.layerGroup().addTo(map);
      const safeMoundsGroup = L.layerGroup().addTo(map);
      const footprintsGroup = L.layerGroup().addTo(map);

      layerGroupsRef.current.provinces = provincesGroup;
      layerGroupsRef.current.stations = stationsGroup;
      layerGroupsRef.current.locations = locationsGroup;
      layerGroupsRef.current.safeMounds = safeMoundsGroup;
      layerGroupsRef.current.footprints = footprintsGroup;

      try {
        const res = await fetch("/geojson/provinces.geojson");
        if (res.ok) {
          const geojsonData = await res.json();
          L.geoJSON(geojsonData, {
            style: () => ({
              color: "#06b6d4",
              weight: 1.5,
              opacity: 0.65,
              fillColor: "#0f2744",
              fillOpacity: 0.15,
              dashArray: "4, 4",
            }),
            onEachFeature: (feature, layer) => {
              const name = feature.properties?.name || "Province";
              const nameKm = feature.properties?.name_km || "";
              layer.bindTooltip(
                `<div class="font-medium text-xs text-cyan-300">${name} (${nameKm})</div>`,
                {
                  permanent: false,
                  direction: "center",
                  className: "province-tooltip",
                },
              );
            },
          }).addTo(provincesGroup);
        }
      } catch (err) {
        console.warn("Province GeoJSON fetch notice:", err);
      }

      setIsLoaded(true);
    }

    initMap();

    return () => {
      isCancelled = true;
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Update base layer cleanly without touching JRC or marker layers
  useEffect(() => {
    const map = mapInstanceRef.current;
    const baseGroup = baseLayerGroupRef.current;
    if (!map || !baseGroup || typeof window === "undefined") return;

    import("leaflet").then((L) => {
      baseGroup.clearLayers();

      if (activeBaseLayer === "dark") {
        L.tileLayer(
          "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
          {
            attribution: "Tiles &copy; Esri",
            maxZoom: 16,
          },
        ).addTo(baseGroup);

        L.tileLayer(
          "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
          {
            attribution: "Tiles &copy; Esri",
            maxZoom: 16,
          },
        ).addTo(baseGroup);
      } else if (activeBaseLayer === "osm") {
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: "&copy; OpenStreetMap contributors",
          maxZoom: 18,
        }).addTo(baseGroup);
      } else {
        L.tileLayer(
          "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
          {
            attribution: "Tiles &copy; Esri",
            maxZoom: 18,
          },
        ).addTo(baseGroup);
      }
    });
  }, [activeBaseLayer]);

  // Toggle JRC Layer
  useEffect(() => {
    const map = mapInstanceRef.current;
    const jrcLayer = layerGroupsRef.current.jrc;
    if (!map || !jrcLayer) return;

    if (jrcVisible) {
      if (!map.hasLayer(jrcLayer)) map.addLayer(jrcLayer);
    } else {
      if (map.hasLayer(jrcLayer)) map.removeLayer(jrcLayer);
    }
  }, [jrcVisible]);

  // Toggle Provinces Layer
  useEffect(() => {
    const map = mapInstanceRef.current;
    const group = layerGroupsRef.current.provinces;
    if (!map || !group) return;

    if (provincesVisible) {
      if (!map.hasLayer(group)) map.addLayer(group);
    } else {
      if (map.hasLayer(group)) map.removeLayer(group);
    }
  }, [provincesVisible]);

  // Render Stations
  useEffect(() => {
    const map = mapInstanceRef.current;
    const stationsGroup = layerGroupsRef.current.stations;
    if (!map || !stationsGroup || !isLoaded) return;

    import("leaflet").then((L) => {
      stationsGroup.clearLayers();

      if (!stationsVisible) return;

      const stationData =
        stations.length > 0
          ? stations
          : [
              {
                id: "station-prek-kdam",
                name: "Prek Kdam Hydrological Station",
                name_km: "ស្ថានីយជលសាស្ត្រព្រែកក្តាម",
                river: "Tonle Sap River",
                lat: 11.8153,
                lon: 104.8064,
                water_level_m: 8.74,
                alarm_level_m: 9.5,
                flood_level_m: 10.0,
                discharge_m3s: 3620,
                trend: "rising",
                status: "active",
              },
              {
                id: "station-kampong-luong",
                name: "Kampong Luong Floating Station",
                name_km: "ស្ថានីយជលសាស្ត្រកំពង់ហ្លួង",
                river: "Tonle Sap Lake",
                lat: 12.2539,
                lon: 104.0486,
                water_level_m: 7.92,
                alarm_level_m: 9.0,
                flood_level_m: 10.5,
                discharge_m3s: 4120,
                trend: "stable",
                status: "active",
              },
              {
                id: "station-kampong-thom",
                name: "Kampong Thom River Gauge",
                name_km: "ស្ថានីយជលសាស្ត្រស្ទឹងសែន កំពង់ធំ",
                river: "Stung Sen River",
                lat: 12.7114,
                lon: 104.8886,
                water_level_m: 12.82,
                alarm_level_m: 13.5,
                flood_level_m: 14.0,
                discharge_m3s: 940,
                trend: "rising",
                status: "active",
              },
            ];

      stationData.forEach((st: any) => {
        const isSelected = selectedStationId === st.id;
        const iconHtml = `
          <div class="relative flex items-center justify-center">
            <span class="absolute inline-flex h-8 w-8 animate-ping rounded-full bg-cyan-400 opacity-40"></span>
            <div class="relative flex h-7 w-7 items-center justify-center rounded-full border-2 ${
              isSelected
                ? "border-white bg-cyan-400 scale-125"
                : "border-cyan-300 bg-cyan-600"
            } shadow-lg text-white">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12h20"/><path d="M20 12v8H4v-8"/><path d="m4 4 16 0"/><path d="M12 4v4"/></svg>
            </div>
          </div>
        `;

        const customIcon = L.divIcon({
          html: iconHtml,
          className: "custom-station-pin",
          iconSize: [32, 32],
          iconAnchor: [16, 16],
        });

        const marker = L.marker([st.lat, st.lon], { icon: customIcon });

        const popupContent = `
          <div class="p-2 min-w-[210px] text-slate-100">
            <div class="flex items-center justify-between border-b border-navy-800 pb-1.5 mb-2">
              <span class="text-xs font-semibold text-cyan-400 uppercase tracking-wider">Hydrometric Gauge</span>
              <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Active</span>
            </div>
            <h4 class="font-bold text-sm text-white mb-0.5">${st.name}</h4>
            <p class="text-xs text-slate-400 mb-2 font-sans">${st.name_km || ""}</p>
            <div class="grid grid-cols-2 gap-2 text-xs bg-navy-950/60 p-2 rounded border border-navy-800 mb-2">
              <div>
                <span class="text-slate-400 block text-[10px]">Water Level</span>
                <span class="font-bold text-cyan-300">${st.water_level_m ?? "7.8"} m</span>
              </div>
              <div>
                <span class="text-slate-400 block text-[10px]">Discharge</span>
                <span class="font-bold text-slate-200">${st.discharge_m3s ?? "3,400"} m³/s</span>
              </div>
              <div>
                <span class="text-slate-400 block text-[10px]">Alarm Level</span>
                <span class="text-amber-400">${st.alarm_level_m ?? "9.5"} m</span>
              </div>
              <div>
                <span class="text-slate-400 block text-[10px]">Trend</span>
                <span class="text-white capitalize">${st.trend || "Stable"}</span>
              </div>
            </div>
            <div class="text-[10px] text-slate-400 flex items-center justify-between">
              <span>${st.lat.toFixed(4)}°N, ${st.lon.toFixed(4)}°E</span>
              <span class="text-cyan-400 cursor-pointer underline">Select &rarr;</span>
            </div>
          </div>
        `;

        marker.bindPopup(popupContent);
        marker.on("click", () => {
          onSelectStation?.(st);
        });

        marker.addTo(stationsGroup);
      });
    });
  }, [stations, selectedStationId, stationsVisible, isLoaded]);

  // Render Provincial + Live-Synced Farmer & Floating Community Risk Pins
  useEffect(() => {
    const map = mapInstanceRef.current;
    const locationsGroup = layerGroupsRef.current.locations;
    if (!map || !locationsGroup || !isLoaded) return;

    import("leaflet").then((L) => {
      locationsGroup.clearLayers();

      if (!riskMarkersVisible) return;

      const getRiskColor = (level: string) => {
        if (level === "very_high") return "#ef4444";
        if (level === "high") return "#f97316";
        if (level === "moderate") return "#f59e0b";
        return "#22c55e";
      };

      const getRiskLabel = (level: string) => {
        if (level === "very_high") return "Very High Risk";
        if (level === "high") return "High Risk";
        if (level === "moderate") return "Moderate Risk";
        return "Low Risk";
      };

      const liveRiskById: Record<string, { level: string; score?: number }> = {
        pursat: { level: "moderate" },
        "kampong-chhnang": { level: "very_high" },
        "siem-reap": { level: "low" },
        battambang: { level: "moderate" },
        "kampong-thom": { level: "moderate" },
      };

      if (riskAssessments.length > 0) {
        riskAssessments.forEach((r) => {
          liveRiskById[r.location_id] = {
            level: r.risk_level,
            score: r.risk_score,
          };
        });
      }

      // 1. Render 5 Provincial Capitals
      MONITORING_LOCATIONS.filter((l) => l.type === "province").forEach(
        (loc) => {
          const liveData = liveRiskById[loc.id] || { level: "low" };
          const color = getRiskColor(liveData.level);
          const isSelected = selectedLocationId === loc.id;

          const circle = L.circleMarker([loc.lat, loc.lon], {
            radius: isSelected ? 15 : 11,
            fillColor: color,
            color: "#ffffff",
            weight: isSelected ? 3 : 2,
            opacity: 0.95,
            fillOpacity: 0.85,
          });

          circle.bindTooltip(
            `<div class="text-xs font-sans text-slate-100">
            <div class="font-bold text-white">${loc.name} (${loc.name_km})</div>
            <div class="text-[11px] text-slate-300">Provincial Hub &bull; ${getRiskLabel(liveData.level)}</div>
          </div>`,
            { direction: "top" },
          );

          circle.bindPopup(`
          <div class="p-2 min-w-[215px] text-slate-100">
            <div class="flex items-center justify-between border-b border-navy-800 pb-1.5 mb-2">
              <span class="text-[10px] font-semibold text-cyan-400 uppercase tracking-wider">Provincial Center</span>
              <span class="px-1.5 py-0.5 rounded text-[10px] font-bold text-white" style="background:${color}">${getRiskLabel(liveData.level)}</span>
            </div>
            <h4 class="font-bold text-sm text-white">${loc.name}</h4>
            <p class="text-xs text-slate-400 mb-2">${loc.name_km}</p>
            <div class="text-[11px] text-slate-300 bg-navy-950/70 p-2 rounded border border-navy-800">
              ${
                liveData.score !== undefined
                  ? `Live AI Risk Index: <strong class="text-white">${(liveData.score * 100).toFixed(0)}%</strong><br/>`
                  : ""
              }Click to filter dashboard telemetry and 3-day AI risk outlook for ${loc.name}.
            </div>
          </div>
        `);

          circle.on("click", () => {
            onSelectLocation?.(loc);
          });

          circle.addTo(locationsGroup);
        },
      );

      // 2. Render 14 Farmer, Agricultural Rice Bowl & Floating Community Pins
      COMMUNITY_RISK_HUBS.forEach((hub) => {
        const directRisk = liveRiskById[hub.id];
        const parentRisk = liveRiskById[hub.provinceId];
        const activeLevel =
          directRisk?.level || parentRisk?.level || hub.fallback_risk;
        const activeScore = directRisk?.score ?? parentRisk?.score;
        const color = getRiskColor(activeLevel);
        const isSelected = selectedLocationId === hub.id;

        const communityCircle = L.circleMarker([hub.lat, hub.lon], {
          radius: isSelected ? 11 : 7.5,
          fillColor: color,
          color: "#0f172a",
          weight: 2,
          opacity: 1,
          fillOpacity: 0.9,
        });

        communityCircle.bindTooltip(
          `<div class="text-xs font-sans text-slate-100">
            <div class="font-bold text-white">${hub.name}</div>
            <div class="text-[11px] text-cyan-300">${hub.name_km}</div>
            <div class="text-[10px] text-slate-300">${hub.livelihood} &bull; ${getRiskLabel(activeLevel)}</div>
          </div>`,
          { direction: "top" },
        );

        communityCircle.bindPopup(`
          <div class="p-2.5 min-w-[235px] text-slate-100">
            <div class="flex items-center justify-between border-b border-navy-800 pb-1.5 mb-2">
              <span class="text-[10px] font-semibold text-amber-300 uppercase tracking-wider">${hub.province}</span>
              <span class="px-1.5 py-0.5 rounded text-[10px] font-bold text-white" style="background:${color}">${getRiskLabel(activeLevel)}</span>
            </div>
            <h4 class="font-bold text-sm text-white leading-snug">${hub.name}</h4>
            <p class="text-xs text-cyan-300 mb-2">${hub.name_km}</p>
            <div class="text-[11px] text-slate-400 mb-1.5">
              <strong class="text-slate-200">Sector:</strong> ${hub.livelihood}
              ${
                activeScore !== undefined
                  ? `<br/><strong class="text-slate-200">Live Basin Index:</strong> ${(activeScore * 100).toFixed(0)}%`
                  : ""
              }
            </div>
            <div class="text-[11px] text-amber-200 bg-navy-950/80 p-2 rounded border border-navy-800 leading-relaxed">
              <strong>Farmer &amp; Community Action:</strong> ${hub.advisory}
            </div>
          </div>
        `);

        communityCircle.addTo(locationsGroup);
      });
    });
  }, [riskAssessments, selectedLocationId, riskMarkersVisible, isLoaded]);

  // Render Designated Safe Elevated Mounds (Tuol Sopheakpheap / ទួលសុវត្ថិភាព)
  useEffect(() => {
    const map = mapInstanceRef.current;
    const safeMoundsGroup = layerGroupsRef.current.safeMounds;
    if (!map || !safeMoundsGroup || !isLoaded) return;

    import("leaflet").then((L) => {
      safeMoundsGroup.clearLayers();

      if (!safeMoundsVisible) return;

      SAFE_ELEVATED_MOUNDS.forEach((mound) => {
        const shieldHtml = `
          <div class="flex h-6 w-6 items-center justify-center rounded-md border-2 border-emerald-200 bg-emerald-600 text-white shadow-md">
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/><path d="m9 12 2 2 4-4"/></svg>
          </div>
        `;

        const moundIcon = L.divIcon({
          html: shieldHtml,
          className: "custom-safe-mound-pin",
          iconSize: [24, 24],
          iconAnchor: [12, 12],
        });

        const marker = L.marker([mound.lat, mound.lon], { icon: moundIcon });

        marker.bindTooltip(
          `<div class="text-xs font-sans text-slate-100">
            <div class="font-bold text-emerald-300">${mound.name}</div>
            <div class="text-[11px] text-white">${mound.name_km}</div>
            <div class="text-[10px] text-slate-300">Elevation: +${mound.elevation_m}m &bull; Safe Evacuation Mound</div>
          </div>`,
          { direction: "top" },
        );

        marker.bindPopup(`
          <div class="p-2.5 min-w-[235px] text-slate-100">
            <div class="flex items-center justify-between border-b border-navy-800 pb-1.5 mb-2">
              <span class="text-[10px] font-semibold text-emerald-400 uppercase tracking-wider">Safe Evacuation Mound</span>
              <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">+${mound.elevation_m}m ASL</span>
            </div>
            <h4 class="font-bold text-sm text-white leading-snug">${mound.name}</h4>
            <p class="text-xs text-emerald-300 mb-2">${mound.name_km}</p>
            <div class="text-[11px] text-slate-300 space-y-1 bg-navy-950/80 p-2 rounded border border-navy-800">
              <div><strong class="text-slate-200">Province:</strong> ${mound.province}</div>
              <div><strong class="text-slate-200">Capacity:</strong> ${mound.capacity}</div>
              <div><strong class="text-slate-200">Facilities:</strong> ${mound.facilities}</div>
            </div>
          </div>
        `);

        marker.addTo(safeMoundsGroup);
      });
    });
  }, [safeMoundsVisible, isLoaded]);

  // Render Satellite Footprints
  useEffect(() => {
    const map = mapInstanceRef.current;
    const footprintsGroup = layerGroupsRef.current.footprints;
    if (!map || !footprintsGroup || !isLoaded) return;

    import("leaflet").then((L) => {
      footprintsGroup.clearLayers();

      if (!footprints || footprints.length === 0) return;

      footprints.forEach((fp) => {
        if (fp.coordinates && fp.coordinates.length > 0) {
          const polygon = L.polygon(fp.coordinates, {
            color: "#a855f7",
            weight: 2,
            opacity: 0.85,
            fillColor: "#9333ea",
            fillOpacity: 0.15,
            dashArray: "6, 6",
          });

          polygon.bindTooltip(
            `<div class="text-xs text-purple-200"><strong>${fp.name || fp.id}</strong><br/>${fp.satellite || "SAR Footprint"}</div>`,
          );
          polygon.addTo(footprintsGroup);
        } else if (fp.bbox) {
          const [minLon, minLat, maxLon, maxLat] = fp.bbox;
          const bounds: [[number, number], [number, number]] = [
            [minLat, minLon],
            [maxLat, maxLon],
          ];
          const rect = L.rectangle(bounds, {
            color: "#a855f7",
            weight: 2,
            opacity: 0.8,
            fillColor: "#9333ea",
            fillOpacity: 0.1,
            dashArray: "4, 4",
          });
          rect.bindTooltip(
            `<div class="text-xs text-purple-200"><strong>${fp.name || fp.id}</strong></div>`,
          );
          rect.addTo(footprintsGroup);
        }
      });
    });
  }, [footprints, isLoaded]);

  // Fly to selected station
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !selectedStationId) return;

    const loc =
      stations.find((s) => s.id === selectedStationId) ||
      MONITORING_LOCATIONS.find((l) => l.id === selectedStationId);

    if (loc && loc.lat && loc.lon) {
      map.flyTo([loc.lat, loc.lon], 10, { duration: 1.2 });
    }
  }, [selectedStationId, stations]);

  const handleResetView = () => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.flyTo(TONLE_SAP_CENTER, 8, { duration: 1 });
    }
  };

  return (
    <div
      className={`relative w-full overflow-hidden rounded-xl border border-navy-800 bg-navy-950 shadow-2xl transition-all ${
        fullscreen ? "fixed inset-0 z-50 rounded-none h-screen" : ""
      } ${className}`}
      style={{ height: fullscreen ? "100vh" : height }}
    >
      {/* Map DOM Container */}
      <div ref={mapContainerRef} className="h-full w-full" />

      {/* Floating Map Controls - Top Left */}
      <div className="absolute top-3 left-3 z-[1000] flex flex-col gap-2">
        {/* Base Layer Switcher */}
        <div className="flex items-center overflow-hidden rounded-lg border border-navy-800 bg-navy-900/90 p-1 shadow-lg backdrop-blur-md">
          <button
            onClick={() => setActiveBaseLayer("dark")}
            className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
              activeBaseLayer === "dark"
                ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Dark Matter
          </button>
          <button
            onClick={() => setActiveBaseLayer("osm")}
            className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
              activeBaseLayer === "osm"
                ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Street Map
          </button>
          <button
            onClick={() => setActiveBaseLayer("satellite")}
            className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
              activeBaseLayer === "satellite"
                ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Satellite
          </button>
        </div>

        {/* Overlay Toggles */}
        <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-navy-800 bg-navy-900/90 p-1.5 shadow-lg backdrop-blur-md">
          <button
            onClick={() => setJrcVisible(!jrcVisible)}
            className={`flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded transition-colors ${
              jrcVisible
                ? "bg-blue-600/30 text-blue-300 border border-blue-500/50"
                : "text-slate-400 hover:text-white"
            }`}
            title="Toggle JRC Global Surface Water Occurrence"
          >
            <Waves className="h-3.5 w-3.5" />
            <span>JRC Water</span>
          </button>

          <button
            onClick={() => setProvincesVisible(!provincesVisible)}
            className={`flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded transition-colors ${
              provincesVisible
                ? "bg-cyan-600/30 text-cyan-300 border border-cyan-500/50"
                : "text-slate-400 hover:text-white"
            }`}
            title="Toggle Provincial Boundaries"
          >
            <Layers className="h-3.5 w-3.5" />
            <span>Provinces</span>
          </button>

          <button
            onClick={() => setStationsVisible(!stationsVisible)}
            className={`flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded transition-colors ${
              stationsVisible
                ? "bg-cyan-600/30 text-cyan-300 border border-cyan-500/50"
                : "text-slate-400 hover:text-white"
            }`}
            title="Toggle Hydro Stations"
          >
            <MapPin className="h-3.5 w-3.5" />
            <span>Stations</span>
          </button>

          <button
            onClick={() => setRiskMarkersVisible(!riskMarkersVisible)}
            className={`flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded transition-colors ${
              riskMarkersVisible
                ? "bg-amber-600/30 text-amber-300 border border-amber-500/50"
                : "text-slate-400 hover:text-white"
            }`}
            title="Toggle Provincial & Community Risk Markers"
          >
            <ShieldAlert className="h-3.5 w-3.5" />
            <span>Risk Pins (19)</span>
          </button>

          <button
            onClick={() => setSafeMoundsVisible(!safeMoundsVisible)}
            className={`flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded transition-colors ${
              safeMoundsVisible
                ? "bg-emerald-600/30 text-emerald-300 border border-emerald-500/50"
                : "text-slate-400 hover:text-white"
            }`}
            title="Toggle Designated Safe Elevated Mounds (Tuol Sopheakpheap)"
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>Safe Mounds (7)</span>
          </button>
        </div>
      </div>

      {/* Floating Map Utility Buttons - Top Right */}
      <div className="absolute top-16 right-3 z-[1000] flex flex-col gap-1.5">
        <button
          onClick={handleResetView}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-navy-800 bg-navy-900/90 text-slate-300 shadow-md backdrop-blur-md hover:bg-navy-800 hover:text-white"
          title="Reset Tonle Sap Basin Extent"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
        <button
          onClick={() => setFullscreen(!fullscreen)}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-navy-800 bg-navy-900/90 text-slate-300 shadow-md backdrop-blur-md hover:bg-navy-800 hover:text-white"
          title={fullscreen ? "Exit Fullscreen" : "Fullscreen Map"}
        >
          <Maximize2 className="h-4 w-4" />
        </button>
      </div>

      {/* Floating Map Legend - Bottom Right */}
      <div className="absolute bottom-3 right-3 z-[1000] max-w-xs rounded-lg border border-navy-800 bg-navy-900/90 p-3 shadow-xl backdrop-blur-md">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
          Basin Hazard Legend
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs text-slate-300">
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500"></span>
            <span>Low Risk</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-amber-500"></span>
            <span>Moderate</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-orange-500"></span>
            <span>High Risk</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-rose-500"></span>
            <span>Very High</span>
          </div>
          <div className="flex items-center gap-1.5 col-span-2 pt-1 border-t border-navy-800">
            <span className="h-2.5 w-2.5 rounded-full bg-cyan-400 ring-2 ring-cyan-400/40 animate-pulse"></span>
            <span>Hydrological Station</span>
          </div>
          <div className="flex items-center gap-1.5 col-span-2">
            <span className="h-2.5 w-2.5 rounded-sm bg-emerald-600 border border-emerald-200"></span>
            <span>Tuol Sopheakpheap (Safe Mound)</span>
          </div>
          <div className="flex items-center gap-1.5 col-span-2">
            <div className="h-2 w-14 rounded bg-gradient-to-r from-cyan-900 via-blue-500 to-blue-300"></div>
            <span className="text-[11px] text-slate-400">JRC Water 0-100%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default TonleSapMap;
