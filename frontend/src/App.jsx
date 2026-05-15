
import React, { useState, useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Polygon, Tooltip, ImageOverlay as LeafletImageOverlay, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './App.css';
import { API_BASE_URL } from './apiConfig.js';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const IMAGE_WIDTH_PX = 1024;
const IMAGE_HEIGHT_PX = 1024;
const IMAGE_SCALE_FACTOR = 1.0125;
const HOUSE_DATA_URL = '/data/socal-fire-house-conditions.json';
const NOMINATIM_SEARCH_URL = 'https://nominatim.openstreetmap.org/search';
const MAP_SEARCH_ZOOM = 18;
const CONDITION_COLORS = {
  no_damage: '#2fbf71',
  minor_damage: '#8ccf3f',
  major_damage: '#f49d37',
  destroyed: '#d64545',
  unknown: '#00c2ff'
};

// Types of queries that can be submitted
const QUERY_TYPES = Object.freeze({
  NA: 'n/a',
  LOCATION: 'location',
  FILTER: 'filter'
});

// Query prefixes and their corresponding types
const QUERY_PREFIXES = Object.freeze({
  '/go ': QUERY_TYPES.LOCATION,
  '/map ': QUERY_TYPES.LOCATION,
  '/filter ': QUERY_TYPES.FILTER
});

function normalizeCondition(rawCondition) {
  if (!rawCondition) {
    return 'unknown';
  }

  const normalized = String(rawCondition)
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_');

  if (normalized.includes('destroy')) {
    return 'destroyed';
  }
  if (normalized.includes('major') || normalized.includes('severe')) {
    return 'major_damage';
  }
  if (normalized.includes('minor')) {
    return 'minor_damage';
  }
  if (normalized.includes('none') || normalized.includes('no_damage') || normalized.includes('undamaged')) {
    return 'no_damage';
  }

  return CONDITION_COLORS[normalized] ? normalized : 'unknown';
}

function conditionToColor(condition) {
  return CONDITION_COLORS[normalizeCondition(condition)] || CONDITION_COLORS.unknown;
}

function isWithinViewport(viewport, lat, lng) {
  if (!viewport || !Number.isFinite(lat) || !Number.isFinite(lng)) {
    return false;
  }

  return (
    lat >= viewport.south &&
    lat <= viewport.north &&
    lng >= viewport.west &&
    lng <= viewport.east
  );
}

function buildDamageSummaryFromVisiblePolygons(polygons, viewport, imageType, conditionVisible) {
  const counts = {
    no_damage: 0,
    minor_damage: 0,
    major_damage: 0,
    destroyed: 0,
    unknown: 0
  };

  if (!viewport || !Array.isArray(polygons) || polygons.length === 0) {
    return { counts, total: 0 };
  }

  const suffix = imageType === 'pre' ? '_pre_disaster.png' : '_post_disaster.png';

  polygons.forEach((polygon) => {
    if (!polygon?.imageId || !String(polygon.imageId).endsWith(suffix)) {
      return;
    }

    const condition = normalizeCondition(polygon.condition);
    if (!conditionVisible?.[condition]) {
      return;
    }

    if (!Array.isArray(polygon.boundary) || polygon.boundary.length < 3) {
      return;
    }

    const boundary = L.latLngBounds(polygon.boundary);
    const center = boundary.getCenter();
    if (!isWithinViewport(viewport, center.lat, center.lng)) {
      return;
    }

    counts[condition] = (counts[condition] || 0) + 1;
  });

  const total = Object.values(counts).reduce((sum, value) => sum + value, 0);
  return { counts, total };
}

function looksLikeLocationQuery(query) {
  if (!query) {
    return false;
  }

  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return false;
  }

  if (normalized.startsWith('/go ') || normalized.startsWith('/map ')) {
    return true;
  }

  if (/\d/.test(normalized)) {
    return true;
  }

  return /(street|st\b|avenue|ave\b|road|rd\b|drive|dr\b|lane|ln\b|court|ct\b|circle|cir\b|boulevard|blvd\b|way\b|place|pl\b|trail|trl\b|highway|hwy\b)/.test(normalized);
}

// // Parses query to determine its type and value
// function parseQuery(input) {
//   const trimmed = String(input || '').trim();
  
//   // Return N/A if query is empty
//   if (!trimmed) {
//     return { type: QUERY_TYPES.NA, value: '' };
//   }

//   // Prefix of query
//   const queryPrefix = trimmed.toLowerCase().split(' ')[0] + ' ';
  
//   // If query prefix is valid, returns query type and query value
//   if (Object.keys(QUERY_PREFIXES).includes(queryPrefix)) {
//     return { type: QUERY_PREFIXES[queryPrefix], value: trimmed.slice(queryPrefix.length).trim() };
//   }

//   // If query prefix is invalid, and:
//   //    - Query value looks like location query: treat as location query.
//   //    - Otherwise: treat as N/A
//   return looksLikeLocationQuery(trimmed) ? { type: QUERY_TYPES.LOCATION, value: trimmed } : { type: QUERY_TYPES.NA, value: '' };
// }

function parseQuery(input) {
  const trimmed = String(input || '').trim();

  if (!trimmed) {
    return { type: QUERY_TYPES.NA, value: '' };
  }

  const normalized = trimmed.toLowerCase();

  if (normalized.startsWith('/go ')) {
    return { type: QUERY_TYPES.LOCATION, value: trimmed.slice(4).trim() };
  }

  if (normalized.startsWith('/map ')) {
    return { type: QUERY_TYPES.LOCATION, value: trimmed.slice(5).trim() };
  }

  if (normalized.startsWith('/filter ')) {
    return { type: QUERY_TYPES.FILTER, value: trimmed.slice(8).trim() };
  }

  return { type: QUERY_TYPES.NA, value: '' };
}

function buildGeocodeRequestUrl(query, bounds, bounded) {
  const params = new URLSearchParams({
    format: 'jsonv2',
    limit: '1',
    countrycodes: 'us',
    q: query
  });

  if (bounded && Array.isArray(bounds) && bounds.length === 2) {
    const southWest = bounds[0];
    const northEast = bounds[1];

    if (Array.isArray(southWest) && Array.isArray(northEast)) {
      const south = Number(southWest[0]);
      const west = Number(southWest[1]);
      const north = Number(northEast[0]);
      const east = Number(northEast[1]);

      if ([south, west, north, east].every(Number.isFinite)) {
        params.set('viewbox', `${west},${north},${east},${south}`);
        params.set('bounded', '1');
      }
    }
  }

  return `${NOMINATIM_SEARCH_URL}?${params.toString()}`;
}

async function geocodeLocationQuery(query, bounds, signal) {
  const requestUrls = [
    buildGeocodeRequestUrl(query, bounds, true),
    buildGeocodeRequestUrl(query, bounds, false)
  ];

  for (let index = 0; index < requestUrls.length; index += 1) {
    const response = await fetch(requestUrls[index], {
      signal,
      headers: {
        Accept: 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Geocoding request failed: ${response.status}`);
    }

    const results = await response.json();
    const firstResult = Array.isArray(results) ? results[0] : null;
    const latitude = Number(firstResult?.lat);
    const longitude = Number(firstResult?.lon);

    if (firstResult && Number.isFinite(latitude) && Number.isFinite(longitude)) {
      return {
        lat: latitude,
        lng: longitude,
        zoom: MAP_SEARCH_ZOOM,
        label: firstResult.display_name || query
      };
    }
  }

  return null;
}

function getImageExtentFromTransform(transform) {
  const [originLng, stepLngX, stepLngY, originLat, stepLatX, stepLatY] = transform;

  const corners = [
    { x: 0, y: 0 },
    { x: IMAGE_WIDTH_PX, y: 0 },
    { x: 0, y: IMAGE_HEIGHT_PX },
    { x: IMAGE_WIDTH_PX, y: IMAGE_HEIGHT_PX }
  ].map((corner) => ({
    lng: originLng + (corner.x * stepLngX) + (corner.y * stepLngY),
    lat: originLat + (corner.x * stepLatX) + (corner.y * stepLatY)
  }));

  const lngValues = corners.map((corner) => corner.lng);
  const latValues = corners.map((corner) => corner.lat);

  const pixelSizeX = (
    (Math.abs(stepLngX) + Math.abs(stepLngX + stepLngY)) / 2
  ) || Number.EPSILON;

  const pixelSizeY = (
    (Math.abs(stepLatY) + Math.abs(stepLatX + stepLatY)) / 2
  ) || Number.EPSILON;

  return {
    south: Math.min(...latValues),
    north: Math.max(...latValues),
    west: Math.min(...lngValues),
    east: Math.max(...lngValues),
    pixelSizeX,
    pixelSizeY
  };
}

function scaleBoundsFromCenter(south, west, north, east, scaleFactor = IMAGE_SCALE_FACTOR) {
  const latCenter = (south + north) / 2;
  const lngCenter = (west + east) / 2;
  const halfLat = ((north - south) / 2) * scaleFactor;
  const halfLng = ((east - west) / 2) * scaleFactor;

  return [
    [latCenter - halfLat, lngCenter - halfLng],
    [latCenter + halfLat, lngCenter + halfLng]
  ];
}

function getImageBoundsFromExtent(extent, scaleFactor = IMAGE_SCALE_FACTOR) {
  const width = extent.east - extent.west;
  const height = extent.north - extent.south;

  const alignedWest = extent.west;
  const alignedNorthEdge = extent.north;
  const alignedEast = alignedWest + width;
  const alignedSouth = alignedNorthEdge - height;

  return scaleBoundsFromCenter(alignedSouth, alignedWest, alignedNorthEdge, alignedEast, scaleFactor);
}

function solve3x3System(matrix, vector) {
  const m = matrix.map((row) => [...row]);
  const v = [...vector];

  for (let pivot = 0; pivot < 3; pivot += 1) {
    let bestRow = pivot;

    for (let row = pivot + 1; row < 3; row += 1) {
      if (Math.abs(m[row][pivot]) > Math.abs(m[bestRow][pivot])) {
        bestRow = row;
      }
    }

    if (Math.abs(m[bestRow][pivot]) < 1e-12) {
      return null;
    }

    if (bestRow !== pivot) {
      [m[pivot], m[bestRow]] = [m[bestRow], m[pivot]];
      [v[pivot], v[bestRow]] = [v[bestRow], v[pivot]];
    }

    const pivotValue = m[pivot][pivot];

    for (let col = pivot; col < 3; col += 1) {
      m[pivot][col] /= pivotValue;
    }
    v[pivot] /= pivotValue;

    for (let row = 0; row < 3; row += 1) {
      if (row === pivot) {
        continue;
      }

      const factor = m[row][pivot];
      if (factor === 0) {
        continue;
      }

      for (let col = pivot; col < 3; col += 1) {
        m[row][col] -= factor * m[pivot][col];
      }
      v[row] -= factor * v[pivot];
    }
  }

  return v;
}

function solveAffineCoefficients(samples, selectTarget) {
  if (!Array.isArray(samples) || samples.length < 3) {
    return null;
  }

  let sxx = 0;
  let sxy = 0;
  let sx1 = 0;
  let syy = 0;
  let sy1 = 0;
  let s11 = 0;

  let stx = 0;
  let sty = 0;
  let st1 = 0;

  samples.forEach((sample) => {
    const x = sample.x;
    const y = sample.y;
    const target = selectTarget(sample);

    sxx += x * x;
    sxy += x * y;
    sx1 += x;
    syy += y * y;
    sy1 += y;
    s11 += 1;

    stx += target * x;
    sty += target * y;
    st1 += target;
  });

  const systemMatrix = [
    [sxx, sxy, sx1],
    [sxy, syy, sy1],
    [sx1, sy1, s11]
  ];

  const rhs = [stx, sty, st1];
  return solve3x3System(systemMatrix, rhs);
}

function parseWktPolygonPoints(wkt) {
  if (typeof wkt !== 'string') {
    return [];
  }

  const match = wkt.match(/POLYGON\s*\(\((.*)\)\)\s*$/i);
  if (!match || !match[1]) {
    return [];
  }

  return match[1]
    .split(',')
    .map((pair) => pair.trim())
    .map((pair) => pair.split(/\s+/).map(Number))
    .filter((point) => point.length >= 2 && Number.isFinite(point[0]) && Number.isFinite(point[1]))
    .map(([x, y]) => ({ x, y }));
}

function buildLabelSamples(labelData) {
  const lngLatFeatures = labelData?.features?.lng_lat;
  const xyFeatures = labelData?.features?.xy;

  if (!Array.isArray(lngLatFeatures) || !Array.isArray(xyFeatures)) {
    return [];
  }

  const lngLatByUid = new Map();
  lngLatFeatures.forEach((feature) => {
    const uid = feature?.properties?.uid;
    if (!uid || typeof feature?.wkt !== 'string') {
      return;
    }
    lngLatByUid.set(uid, feature.wkt);
  });

  const samples = [];

  xyFeatures.forEach((feature) => {
    const uid = feature?.properties?.uid;
    if (!uid || typeof feature?.wkt !== 'string') {
      return;
    }

    const lngLatWkt = lngLatByUid.get(uid);
    if (!lngLatWkt) {
      return;
    }

    const xyPoints = parseWktPolygonPoints(feature.wkt);
    const lngLatPoints = parseWktPolygonPoints(lngLatWkt);
    const count = Math.min(xyPoints.length, lngLatPoints.length);

    for (let i = 0; i < count; i += 1) {
      samples.push({
        x: xyPoints[i].x,
        y: xyPoints[i].y,
        lng: lngLatPoints[i].x,
        lat: lngLatPoints[i].y
      });
    }
  });

  return samples;
}

function deriveTransformFromLabel(labelData) {
  const samples = buildLabelSamples(labelData);

  if (samples.length < 3) {
    return null;
  }

  const lngCoefficients = solveAffineCoefficients(samples, (sample) => sample.lng);
  const latCoefficients = solveAffineCoefficients(samples, (sample) => sample.lat);

  if (!lngCoefficients || !latCoefficients) {
    return null;
  }

  return [
    lngCoefficients[2],
    lngCoefficients[0],
    lngCoefficients[1],
    latCoefficients[2],
    latCoefficients[0],
    latCoefficients[1]
  ];
}

function pixelToLatLng(x, y, transform) {
  if (!Array.isArray(transform) || transform.length < 6 || !Number.isFinite(x) || !Number.isFinite(y)) {
    return null;
  }

  const [originLng, stepLngX, stepLngY, originLat, stepLatX, stepLatY] = transform;

  return {
    lng: originLng + (x * stepLngX) + (y * stepLngY),
    lat: originLat + (x * stepLatX) + (y * stepLatY)
  };
}

function toLatLngPair(pointLike) {
  if (!Array.isArray(pointLike) || pointLike.length < 2) {
    return null;
  }

  const first = Number(pointLike[0]);
  const second = Number(pointLike[1]);

  if (!Number.isFinite(first) || !Number.isFinite(second)) {
    return null;
  }

  // Supports both [lat, lng] and GeoJSON-style [lng, lat].
  if (Math.abs(first) <= 90 && Math.abs(second) <= 180) {
    return [first, second];
  }

  return [second, first];
}

function toPixelXYPair(pointLike) {
  if (!Array.isArray(pointLike) || pointLike.length < 2) {
    return null;
  }

  const x = Number(pointLike[0]);
  const y = Number(pointLike[1]);

  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    return null;
  }

  return [x, y];
}

function normalizeBoundaryLatLng(house, transform) {
  const latLngBoundary = house.boundaryLatLng
    || house.boundary
    || house.polygon
    || house.coordinates
    || null;

  if (Array.isArray(latLngBoundary) && latLngBoundary.length >= 3) {
    const normalized = latLngBoundary
      .map((point) => toLatLngPair(point))
      .filter(Boolean);

    if (normalized.length >= 3) {
      return normalized;
    }
  }

  const pixelBoundary = house.boundaryPixels
    || house.boundary_xy
    || house.polygonPixels
    || house.pixelBoundary
    || house.xyBoundary
    || null;

  if (!Array.isArray(pixelBoundary) || pixelBoundary.length < 3) {
    return null;
  }

  if (!Array.isArray(transform) || transform.length < 6) {
    return null;
  }

  const normalized = pixelBoundary
    .map((point) => toPixelXYPair(point))
    .filter(Boolean)
    .map(([x, y]) => {
      const latLng = pixelToLatLng(x, y, transform);
      return latLng ? [latLng.lat, latLng.lng] : null;
    })
    .filter(Boolean);

  return normalized.length >= 3 ? normalized : null;
}

function buildLabelPolygonsFromLabel(labelData, imageId, transform) {
  const xyFeatures = labelData?.features?.xy;

  if (!Array.isArray(xyFeatures) || xyFeatures.length === 0) {
    return [];
  }

  if (!Array.isArray(transform) || transform.length < 6) {
    return [];
  }

  return xyFeatures
    .map((feature, index) => {
      const points = parseWktPolygonPoints(feature?.wkt);
      if (points.length < 3) {
        return null;
      }

      const boundary = points
        .map((point) => pixelToLatLng(point.x, point.y, transform))
        .filter(Boolean)
        .map((latLng) => [latLng.lat, latLng.lng]);

      if (boundary.length < 3) {
        return null;
      }

      const uid = feature?.properties?.uid || `feature-${index}`;
      const condition = normalizeCondition(feature?.properties?.subtype || 'unknown');

      return {
        id: `${imageId}-${uid}`,
        uid,
        imageId,
        boundary,
        condition
      };
    })
    .filter(Boolean);
}

function LabelPolygonOverlays({ polygons, imageType, conditionVisible }) {
  const suffix = imageType === 'pre' ? '_pre_disaster.png' : '_post_disaster.png';

  if (!Array.isArray(polygons) || polygons.length === 0) {
    return null;
  }

  return polygons
    .filter((polygon) =>
      polygon.imageId &&
      String(polygon.imageId).endsWith(suffix) &&
      conditionVisible[normalizeCondition(polygon.condition)]
    )
    .map((polygon) => {
      const fillColor = conditionToColor(polygon.condition);

      return (
        <Polygon
          key={polygon.id}
          positions={polygon.boundary}
          pathOptions={{
            color: fillColor,
            weight: 1,
            fillColor,
            fillOpacity: 0.2,
            opacity: 0.8
          }}
        >
          <Tooltip direction="top" offset={[0, -4]}>
            {`Type: ${normalizeCondition(polygon.condition).replace(/_/g, ' ')}`}
          </Tooltip>
        </Polygon>
      );
    });
}

function getImagePairKey(imageId) {
  return String(imageId || '').replace(/_(pre|post)_disaster\.png$/i, '');
}

function HouseConditionOverlays({ houses, imageTransformsById, imageType, conditionVisible }) {
  const normalizedHouses = useMemo(() => {
    if (!Array.isArray(houses) || houses.length === 0) {
      return [];
    }

    const suffix = imageType === 'pre' ? '_pre_disaster.png' : '_post_disaster.png';

    return houses
      .map((house, index) => {
        const imageId = house.imageId || house.image_id || house.filename || house.imageName || null;
        const transform = imageId ? imageTransformsById[imageId] : null;

        if (imageId && !String(imageId).endsWith(suffix)) {
          return null;
        }

        const condition = normalizeCondition(house.condition || house.damage || house.damageLevel);
        const boundaryLatLng = normalizeBoundaryLatLng(house, transform);

        if (boundaryLatLng) {
          return {
            id: house.id || `house-${index}`,
            geometryType: 'polygon',
            boundary: boundaryLatLng,
            condition,
            imageId: imageId || null
          };
        }

        const lat = Number(house.lat ?? house.latitude ?? house.yLat);
        const lng = Number(house.lng ?? house.lon ?? house.longitude ?? house.xLng);

        if (Number.isFinite(lat) && Number.isFinite(lng)) {
          return {
            id: house.id || `house-${index}`,
            geometryType: 'point',
            lat,
            lng,
            condition,
            imageId: imageId || null
          };
        }

        const pixelX = Number(house.x ?? house.pixelX ?? house.pixel_x);
        const pixelY = Number(house.y ?? house.pixelY ?? house.pixel_y);

        if (!Number.isFinite(pixelX) || !Number.isFinite(pixelY) || !imageId) {
          return null;
        }

        const latLng = pixelToLatLng(pixelX, pixelY, transform);

        if (!latLng) {
          return null;
        }

        return {
          id: house.id || `house-${index}`,
          geometryType: 'point',
          lat: latLng.lat,
          lng: latLng.lng,
          condition,
          imageId
        };
      })
      .filter(Boolean);
  }, [houses, imageTransformsById, imageType]);

  return normalizedHouses
    .filter((house) => conditionVisible[normalizeCondition(house.condition)])
    .map((house) => {
      const condition = house.condition;
      const fillColor = conditionToColor(condition);

      if (house.geometryType === 'polygon') {
        return (
          <Polygon
            key={house.id}
            positions={house.boundary}
            pathOptions={{
              color: fillColor,
              weight: 1.5,
              fillColor,
              fillOpacity: 0.25,
              opacity: 0.95
            }}
          >
            <Tooltip direction="top" offset={[0, -4]}>
              {`Condition: ${condition.replace(/_/g, ' ')}`}
            </Tooltip>
          </Polygon>
        );
      }

      return (
        <CircleMarker
          key={house.id}
          center={[house.lat, house.lng]}
          radius={4}
          fillColor={fillColor}
          color="#1d2433"
          weight={1}
          opacity={0.95}
          fillOpacity={0.88}
        >
          <Tooltip direction="top" offset={[0, -4]}>
            {`Condition: ${condition.replace(/_/g, ' ')}`}
          </Tooltip>
        </CircleMarker>
      );
    });
}

// Component to enforce map bounds
function MapBoundsController({ bounds }) {
  const map = useMap();

  useEffect(() => {
    if (bounds) {
      map.setMaxBounds(bounds);
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [bounds, map]);

  return null;
}

// Keep Leaflet layout in sync when side panels change width.
function MapResizeController({ chatOpen }) {
  const map = useMap();

  useEffect(() => {
    const rafId = requestAnimationFrame(() => {
      map.invalidateSize({ pan: true, debounceMoveend: true });
    });

    return () => cancelAnimationFrame(rafId);
  }, [chatOpen, map]);

  return null;
}

function MapSearchController({ target }) {
  const map = useMap();

  useEffect(() => {
    if (!target || !Number.isFinite(target.lat) || !Number.isFinite(target.lng)) {
      return;
    }

    map.flyTo([target.lat, target.lng], target.zoom || MAP_SEARCH_ZOOM, {
      animate: true,
      duration: 1.2
    });
  }, [map, target]);

  return null;
}

function MapViewportController({ onViewportChange }) {
  const map = useMap();

  const pushViewport = React.useCallback(() => {
    const bounds = map.getBounds();
    onViewportChange({
      south: bounds.getSouth(),
      west: bounds.getWest(),
      north: bounds.getNorth(),
      east: bounds.getEast(),
      zoom: map.getZoom(),
      updatedAt: Date.now()
    });
  }, [map, onViewportChange]);

  useMapEvents({
    moveend: pushViewport,
    zoomend: pushViewport
  });

  useEffect(() => {
    pushViewport();
  }, [pushViewport]);

  return null;
}

function describeConditionLabel(conditionKey) {
  return conditionKey.replace(/_/g, ' ');
}

function buildPieSlicePath(cx, cy, radius, startAngle, endAngle) {
  const startX = cx + (radius * Math.cos(startAngle));
  const startY = cy + (radius * Math.sin(startAngle));
  const endX = cx + (radius * Math.cos(endAngle));
  const endY = cy + (radius * Math.sin(endAngle));
  const largeArcFlag = endAngle - startAngle > Math.PI ? 1 : 0;

  return `M ${cx} ${cy} L ${startX} ${startY} A ${radius} ${radius} 0 ${largeArcFlag} 1 ${endX} ${endY} Z`;
}

function DamageSummaryPie({ snapshot, onClose }) {
  if (!snapshot) {
    return null;
  }

  const order = ['destroyed', 'major_damage', 'minor_damage', 'no_damage', 'unknown'];
  const total = snapshot.total || 0;
  const sortedLegend = [...order].sort((a, b) => {
    const delta = (snapshot.counts[b] || 0) - (snapshot.counts[a] || 0);
    if (delta !== 0) {
      return delta;
    }

    return order.indexOf(a) - order.indexOf(b);
  });
  const slices = [];
  let angle = -Math.PI / 2;

  order.forEach((key) => {
    const value = snapshot.counts[key] || 0;
    if (value <= 0 || total <= 0) {
      return;
    }

    const nextAngle = angle + ((value / total) * Math.PI * 2);
    slices.push({
      key,
      value,
      color: conditionToColor(key),
      path: buildPieSlicePath(84, 84, 64, angle, nextAngle)
    });
    angle = nextAngle;
  });

  return (
    <div className="damage-chart-overlay" role="dialog" aria-label="Visible house damage chart">
      <div className="damage-chart-header">
        <strong>Visible Houses</strong>
        <button type="button" className="damage-chart-close" onClick={onClose} aria-label="Close damage chart">
          x
        </button>
      </div>

      <div className="damage-chart-total">Total: {total}</div>

      <svg className="damage-chart-svg" viewBox="0 0 168 168" aria-hidden="true">
        {total > 0 ? (
          slices.map((slice) => (
            <path key={slice.key} d={slice.path} fill={slice.color} stroke="rgba(10, 15, 22, 0.9)" strokeWidth="1" />
          ))
        ) : (
          <circle cx="84" cy="84" r="64" fill="rgba(255, 255, 255, 0.14)" />
        )}
        <circle cx="84" cy="84" r="28" fill="rgba(8, 16, 25, 0.95)" />
      </svg>

      <div className="damage-chart-legend" role="list">
        {sortedLegend.map((key) => (
          <div className="damage-chart-legend-item" key={key} role="listitem">
            <span className="damage-chart-dot" style={{ backgroundColor: conditionToColor(key) }} />
            <span>{describeConditionLabel(key)}</span>
            <span className="damage-chart-count">{snapshot.counts[key] || 0}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function FadingImageOverlay({ image, animateOnAdd, onError }) {
  return (
    <LeafletImageOverlay
      url={image.url}
      bounds={image.bounds}
      opacity={0.85}
      className={`disaster-image-overlay ${animateOnAdd ? 'disaster-image-overlay--fade-in' : ''}`}
      interactive={false}
      eventHandlers={{
        error: () => {
          if (onError) {
            onError(image.id);
          }
        }
      }}
    />
  );
}

// Render only overlays in the viewport and chunk them to keep map interactions smooth.
function SocalFireOverlays({ imageType, imageTransforms, availableImageSet, tilePredictions }) {
  const map = useMap();
  const hasInitialFitRef = useRef(false);
  const seenImageIdsRef = useRef(new Set());
  const [viewBounds, setViewBounds] = useState(null);
  const [viewZoom, setViewZoom] = useState(12);
  const [renderCount, setRenderCount] = useState(20);
  const [failedImageIds, setFailedImageIds] = useState(() => new Set());

  const allImages = useMemo(() => {
    if (!imageTransforms || Object.keys(imageTransforms).length === 0) {
      return [];
    }

    const suffix = imageType === 'pre' ? '_pre_disaster.png' : '_post_disaster.png';

    const sourceImages = Object.entries(imageTransforms)
      .filter(([filename]) => filename.startsWith('socal-fire_') && filename.endsWith(suffix))
      .filter(([filename]) => {
        if (!availableImageSet || availableImageSet.size === 0) {
          return true;
        }

        return availableImageSet.has(filename);
      })
      .map(([filename, transformEntry]) => {
        if (!Array.isArray(transformEntry) || transformEntry.length < 6) {
          return null;
        }

        const extent = getImageExtentFromTransform(transformEntry);

        return {
          id: filename,
          url: `/data/train/images/${filename}`,
          extent
        };
      })
      .filter(Boolean);

    return sourceImages.map((image) => {
      return {
        id: image.id,
        url: image.url,
        bounds: getImageBoundsFromExtent(image.extent)
      };
    });
  }, [availableImageSet, imageTransforms, imageType]);

  const visibleImages = useMemo(() => {
    if (!viewBounds) {
      return [];
    }

    return allImages.filter((image) => L.latLngBounds(image.bounds).intersects(viewBounds));
  }, [allImages, viewBounds]);

  const maxVisibleOverlays = useMemo(() => {
    if (viewZoom >= 16) {
      return 500;
    }
    if (viewZoom >= 15) {
      return 320;
    }
    if (viewZoom >= 14) {
      return 180;
    }
    if (viewZoom >= 13) {
      return 80;
    }
    return 0;
  }, [viewZoom]);

  const prioritizedVisibleImages = useMemo(() => {
    if (!viewBounds || maxVisibleOverlays === 0) {
      return [];
    }

    const center = viewBounds.getCenter();

    return visibleImages
      .filter((image) => !failedImageIds.has(image.id))
      .sort((a, b) => {
        const aCenter = L.latLngBounds(a.bounds).getCenter();
        const bCenter = L.latLngBounds(b.bounds).getCenter();
        const aDist = center.distanceTo(aCenter);
        const bDist = center.distanceTo(bCenter);
        return aDist - bDist;
      })
      .slice(0, maxVisibleOverlays);
  }, [failedImageIds, maxVisibleOverlays, viewBounds, visibleImages]);

  useMapEvents({
    moveend: () => setViewBounds(map.getBounds()),
    zoomend: () => {
      setViewBounds(map.getBounds());
      setViewZoom(map.getZoom());
    }
  });

  useEffect(() => {
    setViewBounds(map.getBounds());
    setViewZoom(map.getZoom());
  }, [map, allImages.length]);

  useEffect(() => {
    setRenderCount(20);

    let rafId = null;
    const grow = () => {
      setRenderCount((current) => {
        if (current >= prioritizedVisibleImages.length) {
          return current;
        }

        rafId = requestAnimationFrame(grow);
        return current + 20;
      });
    };

    rafId = requestAnimationFrame(grow);

    return () => {
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }
    };
  }, [prioritizedVisibleImages.length]);

  useEffect(() => {
    if (allImages.length === 0) {
      return;
    }

    const imageBounds = L.latLngBounds(allImages[0].bounds);
    for (let i = 1; i < allImages.length; i += 1) {
      imageBounds.extend(allImages[i].bounds[0]);
      imageBounds.extend(allImages[i].bounds[1]);
    }

    // Fit once per disaster phase switch to avoid jumpy map behavior while panning.
    if (!hasInitialFitRef.current) {
      map.fitBounds(imageBounds, { padding: [50, 50] });
      hasInitialFitRef.current = true;
    }
  }, [allImages, map]);

  useEffect(() => {
    setFailedImageIds(new Set());
  }, [imageType]);

  return prioritizedVisibleImages.slice(0, renderCount).map((image) => {
    const animateOnAdd = !seenImageIdsRef.current.has(image.id);
    if (animateOnAdd) {
      seenImageIdsRef.current.add(image.id);
    }

    return (
      <React.Fragment key={image.id}>
        <FadingImageOverlay
          image={image}
          animateOnAdd={animateOnAdd}
          onError={(imageId) => {
            setFailedImageIds((current) => {
              if (current.has(imageId)) {
                return current;
              }

              const next = new Set(current);
              next.add(imageId);
              return next;
            });
          }}
        />

        {tilePredictions?.[image.id] &&
          image?.bounds &&
          Number.isFinite(image.bounds.south) &&
          Number.isFinite(image.bounds.north) &&
          Number.isFinite(image.bounds.east) &&
          Number.isFinite(image.bounds.west) && (
          <Polygon
            key={`${image.id}__tint`}
            positions={[
              [image.bounds.south, image.bounds.west],
              [image.bounds.south, image.bounds.east],
              [image.bounds.north, image.bounds.east],
              [image.bounds.north, image.bounds.west],
              [image.bounds.south, image.bounds.west],
            ]}
            pathOptions={{
              color: 'transparent',
              fillColor: conditionToColor(tilePredictions[image.id]),
              weight: 0,
              fillOpacity: 0.18,
              opacity: 1,
            }}
            interactive={false}
          />
        )}
      </React.Fragment>
    );
  });
}

// Finds hidden block in text and returns cleaned text and sections of hidden block
function parseHiddenBlock(text) {
  // Get hidden block match
  const blockMatch = text.match(/```([\s\S]*?)```/);

  // If there isn't a hidden block, text is already clean
  if (!blockMatch) {
    return { cleanText: text, hiddenBlockSections: {} };
  }

  
  // Get hidden block and clean text
  const block = blockMatch[1];
  const cleanText = text.replace(blockMatch[0], '').trim();

  // Get individual lines of hidden block
  const lines = block.split('\n').map(l => l.trim());

  // Sections of hidden block
  const hiddenBlockSections = {};
  
  let currentSection = null;
  lines.forEach(line => {
    // If line is empty, skip
    if (!line) return;

    // If line is section header (ALL CAPS), denote new hidden block section
    if (/^[A-Z_]+$/.test(line)) {
      currentSection = line;
      hiddenBlockSections[currentSection] = [];
      return;
    }

    // Push lines in hidden block to proper section
    if (currentSection) {
      hiddenBlockSections[currentSection].push(line);
    }
  });

  return { cleanText, hiddenBlockSections };
}

function App() {
  const [conditionVisible, setConditionVisible] = useState({
    no_damage: true,
    minor_damage: true,
    major_damage: true,
    destroyed: true,
    unknown: true
  });
  const [messages, setMessages] = useState([]);
  const chatMessagesRef = useRef(null);
  const userWasAtBottomRef = useRef(true);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedPolygon, setSelectedPolygon] = useState(null);
  const [imageType, setImageType] = useState('post');
  const [imageTransforms, setImageTransforms] = useState({});
  const [availableImageSet, setAvailableImageSet] = useState(null);
  const [mapBounds, setMapBounds] = useState(null);
  const [houseObservations, setHouseObservations] = useState([]);
  const [labelPolygons, setLabelPolygons] = useState([]);
  const [tilePredictions, setTilePredictions] = useState({});
  const [isChatOpen, setIsChatOpen] = useState(true);
  const [mapSearchTarget, setMapSearchTarget] = useState(null);
  const [mapViewport, setMapViewport] = useState(null);
  const [damageChartSnapshot, setDamageChartSnapshot] = useState(null);
  const [isDamageChartOpen, setIsDamageChartOpen] = useState(false);
  const mapSearchAbortRef = useRef(null);
  const [vlmPostName, setVlmPostName] = useState('');
  const [vlmMode, setVlmMode] = useState('crops');
  const [vlmLoading, setVlmLoading] = useState(false);
  const [vlmError, setVlmError] = useState(null);
  const [vlmResult, setVlmResult] = useState(null);
  const [activeView, setActiveView] = useState('map');
  const [evaluationLoading, setEvaluationLoading] = useState(false);
  const [evaluationError, setEvaluationError] = useState(null);
  const [evaluationData, setEvaluationData] = useState(null);
  const [uploadPreFile, setUploadPreFile] = useState(null);
  const [uploadPostFile, setUploadPostFile] = useState(null);
  const [uploadMode, setUploadMode] = useState('full');
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);

  useEffect(() => {
    const loadAvailableImages = async () => {
      try {
        const response = await fetch('/data/socal-fire-available-images.json');
        if (!response.ok) {
          throw new Error(`Manifest fetch failed: ${response.status}`);
        }

        const data = await response.json();
        const files = Array.isArray(data.files) ? data.files : [];
        setAvailableImageSet(new Set(files));
      } catch (error) {
        console.warn('Could not load available-image manifest; falling back to geotransforms list.', error);
        setAvailableImageSet(null);
      }
    };

    loadAvailableImages();
  }, []);

  useEffect(() => {
    const loadTilePredictions = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/predictions/tiles?phase=both&prefix=socal-fire_`);
        if (!response.ok) {
          throw new Error(`Tile prediction fetch failed: ${response.status}`);
        }

        const data = await response.json();
        setTilePredictions(data?.predictions || {});
      } catch (error) {
        console.warn('Could not load tile predictions for tinting.', error);
        setTilePredictions({});
      }
    };

    loadTilePredictions();
  }, []);

  const vlmPostOptions = useMemo(() => {
    if (!availableImageSet) {
      return [];
    }
    return Array.from(availableImageSet)
      .filter((f) => f.endsWith('_post_disaster.png'))
      .filter((f) => f.startsWith('socal-fire_'))
      .sort();
  }, [availableImageSet]);

  useEffect(() => {
    if (vlmPostOptions.length > 0 && !vlmPostName) {
      setVlmPostName(vlmPostOptions[0]);
    }
  }, [vlmPostOptions, vlmPostName]);

  useEffect(() => {
    if (activeView !== 'evaluation' || evaluationData) {
      return;
    }

    const loadEvaluationMetrics = async () => {
      setEvaluationLoading(true);
      setEvaluationError(null);
      try {
        const res = await fetch(`${API_BASE_URL}/evaluation/metrics`);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          const detail = data.detail;
          const msg = typeof detail === 'string' ? detail : JSON.stringify(detail ?? data);
          throw new Error(msg || 'Could not load evaluation metrics');
        }
        setEvaluationData(data);
      } catch (err) {
        setEvaluationError(err.message || String(err));
      } finally {
        setEvaluationLoading(false);
      }
    };

    loadEvaluationMetrics();
  }, [activeView, evaluationData]);

  const runVlm = async () => {
    if (!vlmPostName) {
      return;
    }
    setVlmLoading(true);
    setVlmError(null);
    setVlmResult(null);
    try {
      const res = await fetch(`${API_BASE_URL}/vlm/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ post_image_name: vlmPostName, mode: vlmMode }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = data.detail;
        const msg = typeof detail === 'string' ? detail : JSON.stringify(detail ?? data);
        throw new Error(msg || 'VLM request failed');
      }
      setVlmResult(data);
    } catch (err) {
      setVlmError(err.message || String(err));
    } finally {
      setVlmLoading(false);
    }
  };

  const runUploadVlm = async () => {
    if (!uploadPreFile || !uploadPostFile) {
      setUploadError('Please upload both pre-disaster and post-disaster images.');
      return;
    }

    setUploadLoading(true);
    setUploadError(null);
    setUploadResult(null);

    try {
      const formData = new FormData();
      formData.append('pre_image', uploadPreFile);
      formData.append('post_image', uploadPostFile);
      formData.append('mode', uploadMode);

      const res = await fetch(`${API_BASE_URL}/vlm/upload-predict`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = data.detail;
        const msg = typeof detail === 'string' ? detail : JSON.stringify(detail ?? data);
        throw new Error(msg || 'Upload VLM request failed');
      }

      setUploadResult(data);
    } catch (err) {
      setUploadError(err.message || String(err));
    } finally {
      setUploadLoading(false);
    }
  };

  useEffect(() => {
    const loadTransformsFromLabels = async () => {
      if (!availableImageSet || availableImageSet.size === 0) {
        setImageTransforms({});
        setLabelPolygons([]);
        return;
      }

      const imageFiles = Array.from(availableImageSet).filter((filename) => filename.startsWith('socal-fire_'));
      const labelEntries = await Promise.all(
        imageFiles.map(async (imageFilename) => {
          const labelFilename = imageFilename.replace(/\.png$/i, '.json');

          try {
            // const response = await fetch(`/data/train/labels/${labelFilename}`);
            // if (!response.ok) {
            //   return null;
            // }

            // const labelData = await response.json();
            const response = await fetch(`/data/train/labels/${labelFilename}`);
            if (!response.ok) {
              return null;
            }

            const contentType = response.headers.get('content-type') || '';
            if (!contentType.includes('application/json')) {
              console.warn(`Label file did not return JSON: ${labelFilename}`);
              return null;
            }

            const labelData = await response.json();
            const transform = deriveTransformFromLabel(labelData);

            if (!transform) {
              return null;
            }

            const polygons = buildLabelPolygonsFromLabel(labelData, imageFilename, transform);

            return {
              imageFilename,
              transform,
              polygons
            };
          } catch (error) {
            console.warn(`Failed to derive transform from ${labelFilename}.`, error);
            return null;
          }
        })
      );

      const nextTransforms = labelEntries.reduce((accumulator, entry) => {
        if (!entry) {
          return accumulator;
        }

        accumulator[entry.imageFilename] = entry.transform;
        return accumulator;
      }, {});

      const nextLabelPolygons = labelEntries.reduce((accumulator, entry) => {
        if (!entry || !Array.isArray(entry.polygons) || entry.polygons.length === 0) {
          return accumulator;
        }

        accumulator.push(...entry.polygons);
        return accumulator;
      }, []);

      // If a matching pre/post pair exists for a house UID, use the post label for both.
      const postConditionByPairAndUid = new Map();
      nextLabelPolygons.forEach((polygon) => {
        const imageId = String(polygon?.imageId || '');
        if (!imageId.endsWith('_post_disaster.png')) {
          return;
        }

        const uid = polygon?.uid;
        if (!uid) {
          return;
        }

        const pairKey = getImagePairKey(imageId);
        postConditionByPairAndUid.set(`${pairKey}::${uid}`, polygon.condition);
      });

      const reconciledLabelPolygons = nextLabelPolygons.map((polygon) => {
        const imageId = String(polygon?.imageId || '');
        if (!imageId.endsWith('_pre_disaster.png')) {
          return polygon;
        }

        const uid = polygon?.uid;
        if (!uid) {
          return polygon;
        }

        const pairKey = getImagePairKey(imageId);
        const postCondition = postConditionByPairAndUid.get(`${pairKey}::${uid}`);

        if (!postCondition) {
          return polygon;
        }

        return {
          ...polygon,
          condition: postCondition
        };
      });

      setImageTransforms(nextTransforms);
      setLabelPolygons(reconciledLabelPolygons);
    };

    loadTransformsFromLabels();
  }, [availableImageSet]);

  useEffect(() => {
    const loadHouseObservations = async () => {
      try {
        const response = await fetch(HOUSE_DATA_URL);
        if (!response.ok) {
          throw new Error(`House observation fetch failed: ${response.status}`);
        }

        const data = await response.json();
        const houses = Array.isArray(data) ? data : (Array.isArray(data.houses) ? data.houses : []);
        setHouseObservations(houses);
      } catch (error) {
        // Keep the app usable when the future data feed is not available yet.
        console.info('House-condition overlay data is not available yet.', error);
        setHouseObservations([]);
      }
    };

    loadHouseObservations();
  }, []);

  useEffect(() => {
    if (!imageTransforms || Object.keys(imageTransforms).length === 0 || !availableImageSet) {
      return;
    }

    // Calculate bounds from all available socal-fire images
    const socalFireFiles = Array.from(availableImageSet).filter(
      filename => filename.startsWith('socal-fire_')
    );

    if (socalFireFiles.length === 0) {
      return;
    }

    let minLat = Infinity, maxLat = -Infinity;
    let minLng = Infinity, maxLng = -Infinity;

    socalFireFiles.forEach(filename => {
      if (imageTransforms[filename]) {
        const extent = getImageExtentFromTransform(imageTransforms[filename]);
        const bounds = getImageBoundsFromExtent(extent);
        const [southWest, northEast] = bounds;
        const ymin = southWest[0];
        const xmin = southWest[1];
        const ymax = northEast[0];
        const xmax = northEast[1];

        minLat = Math.min(minLat, ymin, ymax);
        maxLat = Math.max(maxLat, ymin, ymax);
        minLng = Math.min(minLng, xmin, xmax);
        maxLng = Math.max(maxLng, xmin, xmax);
      }
    });

    // Add padding to bounds
    const latPadding = (maxLat - minLat) * 0.1;
    const lngPadding = (maxLng - minLng) * 0.1;

    setMapBounds([
      [minLat - latPadding, minLng - lngPadding],
      [maxLat + latPadding, maxLng + lngPadding]
    ]);
  }, [imageTransforms, availableImageSet]);

  useEffect(() => {
    return () => {
      if (mapSearchAbortRef.current) {
        mapSearchAbortRef.current.abort();
      }
    };
  }, []);

  const sendMessage = async () => {
    const submittedText = input.trim();
    if (submittedText && !isLoading) {
      const userMessage = { text: submittedText, sender: 'user' };
      setMessages(prev => [...prev, userMessage]);
      setInput('');
      setIsLoading(true);

      try {
        const res = await fetch(`${API_BASE_URL}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          // body: JSON.stringify({ message: submittedText }),
          body: JSON.stringify({
            message: submittedText,
            history: messages.map((msg) => ({
              role: msg.sender === 'user' ? 'user' : 'assistant',
              content: msg.text,
            })),
          }),
        });
        
        const rawText = await res.text();
        console.log('CHAT STATUS:', res.status);
        console.log('CHAT RAW RESPONSE:', rawText);
        
        let data = {};
        try {
          data = rawText ? JSON.parse(rawText) : {};
        } catch (e) {
          throw new Error(`Server returned non-JSON: ${rawText.slice(0, 200)}`);
        }
        
        if (!res.ok) {
          throw new Error(data.detail || `Request failed with status ${res.status}`);
        }
        
        if (!data.response) {
          throw new Error('Missing "response" field from backend');
        }
        
        // Extract clean text and hidden block sections from chatbot message
        const { cleanText, hiddenBlockSections } = parseHiddenBlock(data.response);
        
        setMessages(prev => [...prev, { text: cleanText, sender: 'bot' }]);
        
        // Process queries from hidden block
        for (const q of (hiddenBlockSections.QUERIES || [])) {
          const query = parseQuery(q);

          if (query.type === QUERY_TYPES.LOCATION && query.value) {
            if (mapSearchAbortRef.current) {
              mapSearchAbortRef.current.abort();
            }

            const abortController = new AbortController();
            mapSearchAbortRef.current = abortController;

            const searchResult = await geocodeLocationQuery(query.value, mapBounds, abortController.signal);
            if (searchResult) {
              setMapSearchTarget({
                ...searchResult,
                requestedQuery: query.value,
                searchedAt: Date.now()
              });
              setMessages(prev => [...prev, { text: `Moved map to ${searchResult.label}.`, sender: 'system' }]);
              continue;
            }

            setMessages(prev => [...prev, { text: `Could not find "${query.value}" on the map.`, sender: 'system' }]);
            continue;
          }

          if (query.type === QUERY_TYPES.FILTER && query.value) {
            const queryWords = String(query.value || '')
                .split(/\s+/)
                .filter(Boolean);

            const selectedConditions = new Set(
              queryWords.filter((w) => Object.prototype.hasOwnProperty.call(conditionVisible, w))
            );

            const next = {};
            Object.keys(conditionVisible).forEach((k) => {
              next[k] = selectedConditions.has(k);
            });
            
            setConditionVisible(next);

            setMessages(prev => [
              ...prev,
              {
                text: `Now showing buildings with conditions: ${Object.keys(next).filter(key => next[key]).join(", ")}.`,
                sender: 'system'
              }
            ]);
            
            continue;
          }
        };

        // const res = await fetch(`${API_BASE_URL}/chat`, {
        //   method: 'POST',
        //   headers: { 'Content-Type': 'application/json' },
        //   body: JSON.stringify({ message: submittedText }),
        // });
        // const data = await res.json();
        // setMessages(prev => [...prev, { text: data.response, sender: 'bot' }]);
      // } catch (error) {
      //   if (error?.name === 'AbortError') {
      //     return;
      //   }

      //   setMessages(prev => [...prev, { text: 'Error: Could not complete request', sender: 'bot' }]);
      // } 
    } catch (error) {
      if (error?.name === 'AbortError') {
        return;
      }
    
      console.error('sendMessage failed:', error);
    
      setMessages(prev => [
        ...prev,
        { text: `Error: ${error.message || 'Could not complete request'}`, sender: 'system' }
      ]);
    } finally {
        mapSearchAbortRef.current = null;
        setIsLoading(false);
      }
    }
  };

  const handleChatScroll = () => {
    const el = chatMessagesRef.current;
    if (!el) return;

    const threshold = 50;
    userWasAtBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
  }

  // Automatically scrolls down if there is a new chat message and user is already near bottom of chat sidebar
  useEffect(() => {
    const el = chatMessagesRef.current;
    if (!el) return;

    if (userWasAtBottomRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages]);

  const imageTransformsById = useMemo(() => {
    return imageTransforms || {};
  }, [imageTransforms]);

  const visibleDamageSummary = useMemo(() => {
    return buildDamageSummaryFromVisiblePolygons(
      labelPolygons,
      mapViewport,
      imageType,
      conditionVisible
    );
  }, [conditionVisible, imageType, labelPolygons, mapViewport]);

  const handleDamageChartClick = () => {
    setDamageChartSnapshot({
      ...visibleDamageSummary,
      generatedAt: Date.now()
    });
    setIsDamageChartOpen(true);
  };

  useEffect(() => {
    if (!isDamageChartOpen) {
      return;
    }

    setDamageChartSnapshot({
      ...visibleDamageSummary,
      generatedAt: Date.now()
    });
  }, [isDamageChartOpen, visibleDamageSummary]);

  // Sample polygon data for demonstration
  const polygons = {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { damage: 'green', name: 'Area 1', description: 'Minor damage - Some structural issues but habitable.' },
        geometry: {
          type: 'Polygon',
          coordinates: [[
            [-122.5, 37.7],
            [-122.4, 37.7],
            [-122.4, 37.8],
            [-122.5, 37.8],
            [-122.5, 37.7]
          ]]
        }
      },
      {
        type: 'Feature',
        properties: { damage: 'yellow', name: 'Area 2', description: 'Moderate damage - Requires repairs but safe.' },
        geometry: {
          type: 'Polygon',
          coordinates: [[
            [-122.3, 37.7],
            [-122.2, 37.7],
            [-122.2, 37.8],
            [-122.3, 37.8],
            [-122.3, 37.7]
          ]]
        }
      },
      {
        type: 'Feature',
        properties: { damage: 'orange', name: 'Area 3', description: 'Severe damage - Uninhabitable, major repairs needed.' },
        geometry: {
          type: 'Polygon',
          coordinates: [[
            [-122.1, 37.7],
            [-122.0, 37.7],
            [-122.0, 37.8],
            [-122.1, 37.8],
            [-122.1, 37.7]
          ]]
        }
      },
      {
        type: 'Feature',
        properties: { damage: 'red', name: 'Area 4', description: 'Critical damage - Complete destruction, evacuation required.' },
        geometry: {
          type: 'Polygon',
          coordinates: [[
            [-121.9, 37.7],
            [-121.8, 37.7],
            [-121.8, 37.8],
            [-121.9, 37.8],
            [-121.9, 37.7]
          ]]
        }
      }
    ]
  };

  const getPolygonStyle = (feature) => {
    const damage = feature.properties.damage;
    const colors = {
      green: '#00FF00',
      yellow: '#FFFF00',
      orange: '#FFA500',
      red: '#FF0000'
    };
    return {
      fillColor: colors[damage],
      color: '#000',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.7
    };
  };

  const onEachFeature = (feature, layer) => {
    layer.on({
      click: () => {
        setSelectedPolygon(feature.properties);
      }
    });
  };

  const damageLegendItems = [
    { key: 'no_damage', label: 'No Damage' },
    { key: 'minor_damage', label: 'Minor Damage' },
    { key: 'major_damage', label: 'Major Damage' },
    { key: 'destroyed', label: 'Destroyed' },
    { key: 'unknown', label: 'Unknown' }
  ];

  return (
    <div className="dashboard-layout">
      <div className="dashboard-content">
        <header className="dashboard-header">
          <h1>Damage Assessment Dashboard</h1>
          <p>Southern California Wildfire</p>
        </header>

        <div className="dashboard-main">
          {selectedPolygon && (
            <div className="details-panel">
              <div className="details-panel-body">
                <h3>Details</h3>
                <p><strong>Details</strong></p>
                <p>Details</p>
              </div>
              <button className="chat-panel-button" onClick={() => setSelectedPolygon(null)}>Close</button>
            </div>
          )}

          <div className="map-panel">
            <div className="app-view-switch" role="tablist" aria-label="Application views">
              <button
                type="button"
                className={`app-view-button ${activeView === 'map' ? 'active' : ''}`}
                onClick={() => setActiveView('map')}
              >
                Map
              </button>
              <button
                type="button"
                className={`app-view-button ${activeView === 'evaluation' ? 'active' : ''}`}
                onClick={() => setActiveView('evaluation')}
              >
                Evaluation
              </button>
              <button
                type="button"
                className={`app-view-button ${activeView === 'upload' ? 'active' : ''}`}
                onClick={() => setActiveView('upload')}
              >
                Upload VLM
              </button>
            </div>

            {activeView === 'map' && (
              <>
                <div className="map-stage">
                  <MapContainer
                    center={[34.5, -119.6]}
                    zoom={12}
                    maxZoom={19}
                    maxNativeZoom={19}
                    style={{ flex: 1, width: '100%', border: 'none' }}
                  >
                    <TileLayer
                      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                      attribution='&copy; OpenStreetMap contributors'
                      maxZoom={19}
                      maxNativeZoom={19}
                    />
                    <MapBoundsController bounds={mapBounds} />
                    <MapResizeController chatOpen={isChatOpen} />
                    <MapSearchController target={mapSearchTarget} />
                    <MapViewportController onViewportChange={setMapViewport} />
                    <SocalFireOverlays
                      imageType={imageType}
                      imageTransforms={imageTransforms}
                      availableImageSet={availableImageSet}
                      tilePredictions={tilePredictions}
                    />
                    <LabelPolygonOverlays
                      polygons={labelPolygons}
                      imageType={imageType}
                      conditionVisible={conditionVisible}
                    />
                    <HouseConditionOverlays
                      houses={houseObservations}
                      imageTransformsById={imageTransformsById}
                      imageType={imageType}
                      conditionVisible={conditionVisible}
                    />
                    {mapSearchTarget && (
                      <CircleMarker
                        center={[mapSearchTarget.lat, mapSearchTarget.lng]}
                        radius={8}
                        fillColor="#7ce0ff"
                        color="#08131d"
                        weight={2}
                        opacity={1}
                        fillOpacity={0.95}
                      >
                        <Tooltip direction="top" offset={[0, -8]}>
                          {mapSearchTarget.label}
                        </Tooltip>
                      </CircleMarker>
                    )}
                    <GeoJSON data={polygons} style={getPolygonStyle} onEachFeature={onEachFeature} />
                  </MapContainer>

                  {isDamageChartOpen && (
                    <DamageSummaryPie
                      snapshot={damageChartSnapshot || visibleDamageSummary}
                      onClose={() => setIsDamageChartOpen(false)}
                    />
                  )}

                  <button
                    type="button"
                    className="damage-chart-trigger"
                    onClick={handleDamageChartClick}
                    aria-label="Analyze visible house damage"
                    title="Analyze visible house damage"
                  >
                    <svg viewBox="0 0 32 32" aria-hidden="true" focusable="false">
                      <circle cx="14" cy="14" r="8.75" fill="none" stroke="currentColor" strokeWidth="3.2" />
                      <path d="M20.5 20.5L28 28" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" />
                    </svg>
                  </button>

                  <div className="vlm-panel" role="region" aria-label="GPT-4o Vision VLM">
                    <div className="vlm-panel-title">ResNet-18 (VLM)</div>
                    <label className="vlm-panel-label" htmlFor="vlm-tile-select">Post tile</label>
                    <select
                      id="vlm-tile-select"
                      className="vlm-panel-select"
                      value={vlmPostName}
                      onChange={(e) => setVlmPostName(e.target.value)}
                    >
                      {vlmPostOptions.map((f) => (
                        <option key={f} value={f}>{f}</option>
                      ))}
                    </select>
                    <label className="vlm-panel-label vlm-panel-row" htmlFor="vlm-mode-select">
                      <span>Mode</span>
                      <select
                        id="vlm-mode-select"
                        className="vlm-panel-select vlm-panel-select--narrow"
                        value={vlmMode}
                        onChange={(e) => setVlmMode(e.target.value)}
                      >
                        <option value="crops">Building crops (labels)</option>
                        <option value="full">Full tile images</option>
                      </select>
                    </label>
                    <button type="button" className="vlm-panel-button" onClick={runVlm} disabled={vlmLoading || !vlmPostName}>
                      {vlmLoading ? 'Running…' : 'Run VLM'}
                    </button>
                    {vlmError && <p className="vlm-panel-error">{vlmError}</p>}
                    {vlmResult && (
                      <div className="vlm-panel-result">
                        <div><strong>VLM:</strong> {vlmResult.label}</div>
                        {vlmResult.resnet_label ? (
                          <div><strong>ResNet (batch):</strong> {vlmResult.resnet_label}</div>
                        ) : null}
                        <div className="vlm-panel-meta">mode: {vlmResult.mode}</div>
                      </div>
                    )}
                  </div>

                  <div className="damage-legend-overlay" role="note" aria-label="Damage class legend">
                    {damageLegendItems.map((item) => (
                      <div key={item.key} className="damage-legend-item">
                        <span
                          style={{
                            width: '12px',
                            height: '12px',
                            borderRadius: '50%',
                            backgroundColor: conditionToColor(item.key),
                            border: '1px solid rgba(255, 255, 255, 0.8)'
                          }}
                        />
                        {item.label}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="phase-switch-bar">
                  <div className="phase-switch" role="group" aria-label="Switch between pre and post disaster imagery">
                    <button
                      type="button"
                      className={`phase-switch-option ${imageType === 'pre' ? 'active' : ''}`}
                      onClick={() => setImageType('pre')}
                    >
                      Before
                    </button>
                    <button
                      type="button"
                      className={`phase-switch-option ${imageType === 'post' ? 'active' : ''}`}
                      onClick={() => setImageType('post')}
                    >
                      After
                    </button>
                  </div>
                </div>
              </>
            )}

            {activeView === 'evaluation' && (
              <div className="evaluation-panel">
                <h2>Model Evaluation</h2>
                {evaluationLoading && <p>Loading evaluation metrics...</p>}
                {evaluationError && <p className="vlm-panel-error">{evaluationError}</p>}
                {evaluationData && !evaluationLoading && (
                  <>
                    <div className="evaluation-summary-grid">
                      <div className="evaluation-summary-card">
                        <div className="evaluation-summary-label">Accuracy</div>
                        <div className="evaluation-summary-value">
                          {(Number(evaluationData.summary?.accuracy || 0) * 100).toFixed(2)}%
                        </div>
                      </div>
                      <div className="evaluation-summary-card">
                        <div className="evaluation-summary-label">Evaluated</div>
                        <div className="evaluation-summary-value">{evaluationData.summary?.evaluated_rows ?? 0}</div>
                      </div>
                      <div className="evaluation-summary-card">
                        <div className="evaluation-summary-label">Total rows</div>
                        <div className="evaluation-summary-value">{evaluationData.summary?.total_rows ?? 0}</div>
                      </div>
                    </div>

                    <div className="evaluation-meta">
                      Source: {evaluationData.source_csv}
                      {' | '}
                      Excluded: unclassified={evaluationData.summary?.excluded?.unclassified_ground_truth ?? 0}, unclear={evaluationData.summary?.excluded?.unclear_prediction ?? 0}, invalid={evaluationData.summary?.excluded?.invalid_format ?? 0}
                    </div>

                    <h3>Confusion Matrix</h3>
                    <div className="evaluation-table-wrap">
                      <table className="evaluation-table">
                        <thead>
                          <tr>
                            <th>Ground Truth \\ Pred</th>
                            {(evaluationData.labels || []).map((label) => (
                              <th key={`cm-h-${label}`}>{label}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {(evaluationData.confusion_matrix || []).map((row, rIdx) => (
                            <tr key={`cm-r-${rIdx}`}>
                              <th>{evaluationData.labels?.[rIdx] || `row-${rIdx}`}</th>
                              {row.map((value, cIdx) => (
                                <td key={`cm-c-${rIdx}-${cIdx}`}>{value}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    <h3>Per-class Metrics</h3>
                    <div className="evaluation-table-wrap">
                      <table className="evaluation-table">
                        <thead>
                          <tr>
                            <th>Label</th>
                            <th>Precision</th>
                            <th>Recall</th>
                            <th>F1</th>
                            <th>Support</th>
                            <th>Predicted</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(evaluationData.per_class || []).map((row) => (
                            <tr key={`pc-${row.label}`}>
                              <td>{row.label}</td>
                              <td>{row.precision}</td>
                              <td>{row.recall}</td>
                              <td>{row.f1}</td>
                              <td>{row.support}</td>
                              <td>{row.predicted_count}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </div>
            )}

            {activeView === 'upload' && (
              <div className="upload-vlm-panel">
                <h2>Upload Pre/Post Images (VLM)</h2>
                <p className="evaluation-meta">
                  Upload local pre-disaster and post-disaster images to run live damage assessment.
                </p>
                <div className="upload-vlm-grid">
                  <label className="vlm-panel-label" htmlFor="upload-pre-image">
                    Pre-disaster image
                    <input
                      id="upload-pre-image"
                      className="upload-vlm-input"
                      type="file"
                      accept=".png,.jpg,.jpeg,.webp,image/*"
                      onChange={(e) => setUploadPreFile(e.target.files?.[0] || null)}
                    />
                  </label>
                  <label className="vlm-panel-label" htmlFor="upload-post-image">
                    Post-disaster image
                    <input
                      id="upload-post-image"
                      className="upload-vlm-input"
                      type="file"
                      accept=".png,.jpg,.jpeg,.webp,image/*"
                      onChange={(e) => setUploadPostFile(e.target.files?.[0] || null)}
                    />
                  </label>
                </div>

                <label className="vlm-panel-label vlm-panel-row" htmlFor="upload-mode-select">
                  <span>Mode</span>
                  <select
                    id="upload-mode-select"
                    className="vlm-panel-select vlm-panel-select--narrow"
                    value={uploadMode}
                    onChange={(e) => setUploadMode(e.target.value)}
                  >
                    <option value="full">Full image pair</option>
                    <option value="crops">Crops (falls back to full for uploads)</option>
                  </select>
                </label>

                <button
                  type="button"
                  className="vlm-panel-button upload-vlm-button"
                  onClick={runUploadVlm}
                  disabled={uploadLoading || !uploadPreFile || !uploadPostFile}
                >
                  {uploadLoading ? 'Running…' : 'Run Upload VLM'}
                </button>

                {uploadError && <p className="vlm-panel-error">{uploadError}</p>}
                {uploadResult && (
                  <div className="vlm-panel-result">
                    <div><strong>Prediction:</strong> {uploadResult.label}</div>
                    <div className="vlm-panel-meta">
                      mode: {uploadResult.mode} | pre: {uploadResult.pre_filename} | post: {uploadResult.post_filename}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {isChatOpen && (
        <div className="chat-sidebar">
          <button
            type="button"
            onClick={() => setIsChatOpen(false)}
            className="chat-panel-button chat-close-button"
          >
            Hide
          </button>

          {/* <div className="chat-messages" ref={chatMessagesRef} onScroll={handleChatScroll}>
            {messages.map((msg, index) => (
              <div key={index} className={`chat-message-row chat-message-${msg.sender}`}>
                <span className={`chat-bubble chat-bubble-${msg.sender}`}>{msg.text}</span>
              </div>
            ))}
          </div> */}
          <div className="chat-messages" ref={chatMessagesRef} onScroll={handleChatScroll}>
            {messages.map((msg, index) => (
              <div key={index} className={`chat-message-row chat-message-${msg.sender}`}>
                <div className={`chat-bubble chat-bubble-${msg.sender}`}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.text}
                  </ReactMarkdown>
                </div>
              </div>
            ))}
          </div>

          <div className="chat-input-row">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
              className="chat-input"
              placeholder="Ask a question..."
              disabled={isLoading}
            />
            <button className="chat-panel-button" onClick={sendMessage} disabled={isLoading}>
              {isLoading ? 'Sending...' : 'Send'}
            </button>
          </div>
        </div>
      )}

      {!isChatOpen && (
        <button
          type="button"
          className="chat-open-toggle"
          onClick={() => setIsChatOpen(true)}
        >
          Chat
        </button>
      )}
    </div>
  );
}

export default App
