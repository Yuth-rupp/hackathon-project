'use client';

import React, { useEffect, useRef, useState } from 'react';
import { MONITORING_LOCATIONS, TONLE_SAP_CENTER } from '@/lib/constants';
import { Station, RiskAssessment, MonitoringLocation } from '@/types';
import { Layers, MapPin, Waves, ShieldAlert, Maximize2, RefreshCw } from 'lucide-react';

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

export function TonleSapMap({
  selectedStationId,
  selectedLocationId,
  onSelectStation,
  onSelectLocation,
  stations = [],
  riskAssessments = [],
  footprints = [],
  showJRCWater = true,
  className = '',
  height = '540px',
}: TonleSapMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const layerGroupsRef = useRef<{
    stations?: any;
    locations?: any;
    provinces?: any;
    jrc?: any;
    footprints?: any;
  }>({});

  const [activeBaseLayer, setActiveBaseLayer] = useState<'dark' | 'osm' | 'satellite'>('dark');
  const [jrcVisible, setJrcVisible] = useState(showJRCWater);
  const [provincesVisible, setProvincesVisible] = useState(true);
  const [stationsVisible, setStationsVisible] = useState(true);
  const [riskMarkersVisible, setRiskMarkersVisible] = useState(true);
  const [isLoaded, setIsLoaded] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);

  // Initialize Leaflet Map
  useEffect(() => {
    let isCancelled = false;

    async function initMap() {
      if (typeof window === 'undefined' || !mapContainerRef.current) return;
      if (mapInstanceRef.current) return; // already initialized

      // Dynamically import Leaflet
      const L = (await import('leaflet')).default;

      if (isCancelled || !mapContainerRef.current) return;

      // Base layers
      const darkLayer = L.tileLayer(
        'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        {
          attribution: '&copy; CartoDB &copy; OpenStreetMap contributors',
          maxZoom: 18,
          subdomains: 'abcd',
        }
      );

      const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 18,
      });

      const satLayer = L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        {
          attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye',
          maxZoom: 18,
        }
      );

      // JRC Water Occurrence Layer
      const jrcWaterLayer = L.tileLayer(
        'https://storage.googleapis.com/global-surface-water/tiles2021/occurrence/{z}/{x}/{y}.png',
        {
          opacity: 0.75,
          attribution: 'EC JRC / Google Earth Engine (Global Surface Water)',
          maxZoom: 14,
        }
      );

      // Create map
      const map = L.map(mapContainerRef.current, {
        center: TONLE_SAP_CENTER,
        zoom: 8,
        minZoom: 6,
        maxZoom: 16,
        layers: [darkLayer],
        zoomControl: false,
      });

      // Position Zoom Control top-right
      L.control.zoom({ position: 'topright' }).addTo(map);

      // Save references
      mapInstanceRef.current = map;
      layerGroupsRef.current.jrc = jrcWaterLayer;

      if (jrcVisible) {
        jrcWaterLayer.addTo(map);
      }

      // Feature layer groups
      const provincesGroup = L.layerGroup().addTo(map);
      const stationsGroup = L.layerGroup().addTo(map);
      const locationsGroup = L.layerGroup().addTo(map);
      const footprintsGroup = L.layerGroup().addTo(map);

      layerGroupsRef.current.provinces = provincesGroup;
      layerGroupsRef.current.stations = stationsGroup;
      layerGroupsRef.current.locations = locationsGroup;
      layerGroupsRef.current.footprints = footprintsGroup;

      // Load GeoJSON Province boundaries
      try {
        const res = await fetch('/geojson/provinces.geojson');
        if (res.ok) {
          const geojsonData = await res.json();
          L.geoJSON(geojsonData, {
            style: () => ({
              color: '#06b6d4',
              weight: 1.5,
              opacity: 0.65,
              fillColor: '#0f2744',
              fillOpacity: 0.15,
              dashArray: '4, 4',
            }),
            onEachFeature: (feature, layer) => {
              const name = feature.properties?.name || 'Province';
              const nameKm = feature.properties?.name_km || '';
              layer.bindTooltip(
                `<div class="font-medium text-xs text-cyan-300">${name} (${nameKm})</div>`,
                { permanent: false, direction: 'center', className: 'province-tooltip' }
              );
            },
          }).addTo(provincesGroup);
        }
      } catch (err) {
        console.warn('Province GeoJSON fetch notice:', err);
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

  // Update base layer
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || typeof window === 'undefined') return;

    import('leaflet').then((L) => {
      // Remove any previous base tile layers
      map.eachLayer((layer: any) => {
        if (layer._url && !layer._url.includes('global-surface-water')) {
          map.removeLayer(layer);
        }
      });

      let nextLayer;
      if (activeBaseLayer === 'dark') {
        nextLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
          attribution: '&copy; CartoDB &copy; OpenStreetMap',
          maxZoom: 18,
        });
      } else if (activeBaseLayer === 'osm') {
        nextLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '&copy; OpenStreetMap',
          maxZoom: 18,
        });
      } else {
        nextLayer = L.tileLayer(
          'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
          {
            attribution: 'Tiles &copy; Esri',
            maxZoom: 18,
          }
        );
      }
      nextLayer.addTo(map);
      nextLayer.bringToBack();
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

    import('leaflet').then((L) => {
      stationsGroup.clearLayers();

      if (!stationsVisible) return;

      const stationData =
        stations.length > 0
          ? stations
          : [
              {
                id: 'station-prek-kdam',
                name: 'Prek Kdam Hydrological Station',
                name_km: 'ស្ថានីយជលសាស្ត្រព្រែកក្តាម',
                river: 'Tonle Sap River',
                lat: 11.8153,
                lon: 104.8064,
                water_level_m: 8.74,
                alarm_level_m: 9.5,
                flood_level_m: 10.0,
                discharge_m3s: 3620,
                trend: 'rising',
                status: 'active',
              },
              {
                id: 'station-kampong-luong',
                name: 'Kampong Luong Floating Station',
                name_km: 'ស្ថានីយជលសាស្ត្រកំពង់ហ្លួង',
                river: 'Tonle Sap Lake',
                lat: 12.2539,
                lon: 104.0486,
                water_level_m: 7.92,
                alarm_level_m: 9.0,
                flood_level_m: 10.5,
                discharge_m3s: 4120,
                trend: 'stable',
                status: 'active',
              },
              {
                id: 'station-kampong-thom',
                name: 'Kampong Thom River Gauge',
                name_km: 'ស្ថានីយជលសាស្ត្រស្ទឹងសែន កំពង់ធំ',
                river: 'Stung Sen River',
                lat: 12.7114,
                lon: 104.8886,
                water_level_m: 12.82,
                alarm_level_m: 13.5,
                flood_level_m: 14.0,
                discharge_m3s: 940,
                trend: 'rising',
                status: 'active',
              },
            ];

      stationData.forEach((st: any) => {
        const isSelected = selectedStationId === st.id;
        const iconHtml = `
          <div class="relative flex items-center justify-center">
            <span class="absolute inline-flex h-8 w-8 animate-ping rounded-full bg-cyan-400 opacity-40"></span>
            <div class="relative flex h-7 w-7 items-center justify-center rounded-full border-2 ${
              isSelected ? 'border-white bg-cyan-400 scale-125' : 'border-cyan-300 bg-cyan-600'
            } shadow-lg text-white">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12h20"/><path d="M20 12v8H4v-8"/><path d="m4 4 16 0"/><path d="M12 4v4"/></svg>
            </div>
          </div>
        `;

        const customIcon = L.divIcon({
          html: iconHtml,
          className: 'custom-station-pin',
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
            <p class="text-xs text-slate-400 mb-2 font-sans">${st.name_km || ''}</p>
            <div class="grid grid-cols-2 gap-2 text-xs bg-navy-950/60 p-2 rounded border border-navy-800 mb-2">
              <div>
                <span class="text-slate-400 block text-[10px]">Water Level</span>
                <span class="font-bold text-cyan-300">${st.water_level_m ?? '7.8'} m</span>
              </div>
              <div>
                <span class="text-slate-400 block text-[10px]">Discharge</span>
                <span class="font-bold text-slate-200">${st.discharge_m3s ?? '3,400'} m³/s</span>
              </div>
              <div>
                <span class="text-slate-400 block text-[10px]">Alarm Level</span>
                <span class="text-amber-400">${st.alarm_level_m ?? '9.5'} m</span>
              </div>
              <div>
                <span class="text-slate-400 block text-[10px]">Trend</span>
                <span class="text-white capitalize">${st.trend || 'Stable'}</span>
              </div>
            </div>
            <div class="text-[10px] text-slate-400 flex items-center justify-between">
              <span>${st.lat.toFixed(4)}°N, ${st.lon.toFixed(4)}°E</span>
              <span class="text-cyan-400 cursor-pointer underline">Select &rarr;</span>
            </div>
          </div>
        `;

        marker.bindPopup(popupContent);
        marker.on('click', () => {
          onSelectStation?.(st);
        });

        marker.addTo(stationsGroup);
      });
    });
  }, [stations, selectedStationId, stationsVisible, isLoaded]);

  // Render Risk Circles for Monitoring Locations
  useEffect(() => {
    const map = mapInstanceRef.current;
    const locationsGroup = layerGroupsRef.current.locations;
    if (!map || !locationsGroup || !isLoaded) return;

    import('leaflet').then((L) => {
      locationsGroup.clearLayers();

      if (!riskMarkersVisible) return;

      const riskMap: Record<string, string> = {
        'pursat': '#f59e0b', // moderate
        'kampong-chhnang': '#ef4444', // high / very high
        'siem-reap': '#22c55e', // low
        'battambang': '#f59e0b', // moderate
        'kampong-thom': '#f59e0b', // moderate
      };

      // Match dynamic risk assessments if provided
      if (riskAssessments.length > 0) {
        riskAssessments.forEach((r) => {
          const color =
            r.risk_level === 'very_high'
              ? '#ef4444'
              : r.risk_level === 'high'
              ? '#f97316'
              : r.risk_level === 'moderate'
              ? '#f59e0b'
              : '#22c55e';
          riskMap[r.location_id] = color;
        });
      }

      MONITORING_LOCATIONS.filter((l) => l.type === 'province').forEach((loc) => {
        const color = riskMap[loc.id] || '#22c55e';
        const isSelected = selectedLocationId === loc.id;

        const circle = L.circleMarker([loc.lat, loc.lon], {
          radius: isSelected ? 16 : 12,
          fillColor: color,
          color: '#ffffff',
          weight: isSelected ? 3 : 1.5,
          opacity: 0.9,
          fillOpacity: 0.7,
        });

        const tooltip = `
          <div class="text-xs font-sans text-slate-100">
            <div class="font-bold text-white">${loc.name} (${loc.name_km})</div>
            <div class="text-[11px] text-slate-300">Risk Assessment Point</div>
          </div>
        `;
        circle.bindTooltip(tooltip, { direction: 'top' });

        circle.on('click', () => {
          onSelectLocation?.(loc);
        });

        circle.addTo(locationsGroup);
      });
    });
  }, [riskAssessments, selectedLocationId, riskMarkersVisible, isLoaded]);

  // Render Satellite Footprints
  useEffect(() => {
    const map = mapInstanceRef.current;
    const footprintsGroup = layerGroupsRef.current.footprints;
    if (!map || !footprintsGroup || !isLoaded) return;

    import('leaflet').then((L) => {
      footprintsGroup.clearLayers();

      if (!footprints || footprints.length === 0) return;

      footprints.forEach((fp) => {
        if (fp.coordinates && fp.coordinates.length > 0) {
          const polygon = L.polygon(fp.coordinates, {
            color: '#a855f7',
            weight: 2,
            opacity: 0.85,
            fillColor: '#9333ea',
            fillOpacity: 0.15,
            dashArray: '6, 6',
          });

          polygon.bindTooltip(
            `<div class="text-xs text-purple-200"><strong>${fp.name || fp.id}</strong><br/>${fp.satellite || 'SAR Footprint'}</div>`
          );
          polygon.addTo(footprintsGroup);
        } else if (fp.bbox) {
          // BBox: [minLon, minLat, maxLon, maxLat]
          const [minLon, minLat, maxLon, maxLat] = fp.bbox;
          const bounds: [[number, number], [number, number]] = [
            [minLat, minLon],
            [maxLat, maxLon],
          ];
          const rect = L.rectangle(bounds, {
            color: '#a855f7',
            weight: 2,
            opacity: 0.8,
            fillColor: '#9333ea',
            fillOpacity: 0.1,
            dashArray: '4, 4',
          });
          rect.bindTooltip(
            `<div class="text-xs text-purple-200"><strong>${fp.name || fp.id}</strong></div>`
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
        fullscreen ? 'fixed inset-0 z-50 rounded-none h-screen' : ''
      } ${className}`}
      style={{ height: fullscreen ? '100vh' : height }}
    >
      {/* Map DOM Container */}
      <div ref={mapContainerRef} className="h-full w-full" />

      {/* Floating Map Controls - Top Left */}
      <div className="absolute top-3 left-3 z-[1000] flex flex-col gap-2">
        {/* Base Layer Switcher */}
        <div className="flex items-center overflow-hidden rounded-lg border border-navy-800 bg-navy-900/90 p-1 shadow-lg backdrop-blur-md">
          <button
            onClick={() => setActiveBaseLayer('dark')}
            className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
              activeBaseLayer === 'dark'
                ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Dark Matter
          </button>
          <button
            onClick={() => setActiveBaseLayer('osm')}
            className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
              activeBaseLayer === 'osm'
                ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Street Map
          </button>
          <button
            onClick={() => setActiveBaseLayer('satellite')}
            className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
              activeBaseLayer === 'satellite'
                ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40'
                : 'text-slate-400 hover:text-white'
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
                ? 'bg-blue-600/30 text-blue-300 border border-blue-500/50'
                : 'text-slate-400 hover:text-white'
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
                ? 'bg-cyan-600/30 text-cyan-300 border border-cyan-500/50'
                : 'text-slate-400 hover:text-white'
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
                ? 'bg-emerald-600/30 text-emerald-300 border border-emerald-500/50'
                : 'text-slate-400 hover:text-white'
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
                ? 'bg-amber-600/30 text-amber-300 border border-amber-500/50'
                : 'text-slate-400 hover:text-white'
            }`}
            title="Toggle Risk Markers"
          >
            <ShieldAlert className="h-3.5 w-3.5" />
            <span>Risk Pins</span>
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
          title={fullscreen ? 'Exit Fullscreen' : 'Fullscreen Map'}
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
            <div className="h-2 w-14 rounded bg-gradient-to-r from-cyan-900 via-blue-500 to-blue-300"></div>
            <span className="text-[11px] text-slate-400">JRC Water 0-100%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default TonleSapMap;
