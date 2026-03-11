
import React, { useState, useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Polygon, Tooltip, ImageOverlay as LeafletImageOverlay, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './App.css';

const IMAGE_WIDTH_PX = 1024;
const IMAGE_HEIGHT_PX = 1024;
const IMAGE_SCALE_FACTOR = 1.0125;
const HOUSE_DATA_URL = '/data/socal-fire-house-conditions.json';
const CONDITION_COLORS = {
  no_damage: '#2fbf71',
  minor_damage: '#8ccf3f',
  major_damage: '#f49d37',
  destroyed: '#d64545',
  unknown: '#00c2ff'
};

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

function LabelPolygonOverlays({ polygons, imageType }) {
  const suffix = imageType === 'pre' ? '_pre_disaster.png' : '_post_disaster.png';

  if (!Array.isArray(polygons) || polygons.length === 0) {
    return null;
  }

  return polygons
    .filter((polygon) => polygon.imageId && String(polygon.imageId).endsWith(suffix))
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

function HouseConditionOverlays({ houses, imageTransformsById, imageType }) {
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

  return normalizedHouses.map((house) => {
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
function SocalFireOverlays({ imageType, imageTransforms, availableImageSet }) {
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
      <FadingImageOverlay
        key={image.id}
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
    );
  });
}

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedPolygon, setSelectedPolygon] = useState(null);
  const [imageType, setImageType] = useState('post');
  const [imageTransforms, setImageTransforms] = useState({});
  const [availableImageSet, setAvailableImageSet] = useState(null);
  const [mapBounds, setMapBounds] = useState(null);
  const [houseObservations, setHouseObservations] = useState([]);
  const [labelPolygons, setLabelPolygons] = useState([]);
  const [isChatOpen, setIsChatOpen] = useState(true);

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
            const response = await fetch(`/data/train/labels/${labelFilename}`);
            if (!response.ok) {
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

  const sendMessage = async () => {
    if (input.trim() && !isLoading) {
      const userMessage = { text: input, sender: 'user' };
      setMessages(prev => [...prev, userMessage]);
      setInput('');
      setIsLoading(true);
      try {
        const res = await fetch('http://localhost:3001/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: input }),
        });
        const data = await res.json();
        setMessages(prev => [...prev, { text: data.response, sender: 'bot' }]);
      } catch (error) {
        setMessages(prev => [...prev, { text: 'Error: Could not connect to backend', sender: 'bot' }]);
      } finally {
        setIsLoading(false);
      }
    }
  };

  const imageTransformsById = useMemo(() => {
    return imageTransforms || {};
  }, [imageTransforms]);

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
    <div style={{ width: '100%', height: '90vh', display: 'flex', flexDirection: 'column' }}>
      <h1>Damage Assessment Dashboard</h1>
      <div style={{ display: 'flex', flex: 1, position: 'relative' }}>
        {selectedPolygon && (
          <div style={{ width: '300px', display: 'flex', flexDirection: 'column', border: '1px solid #ddd', borderRadius: '10px', margin: '10px' }}>
            <div style={{ flex: 1, overflowY: 'auto', padding: '10px' }}>
              <h3>Details</h3>
              <p><strong>Details</strong></p>
              <p>Details</p>
            </div>
            <button onClick={() => setSelectedPolygon(null)} style={{ padding: '8px 16px', margin: '10px' }}>Close</button>
          </div>
        )}
        <div style={{ flex: 1.5, display: 'flex', flexDirection: 'column', minWidth: 0, margin: '0 10px' }}>
          <MapContainer 
            center={[34.5, -119.6]} 
            zoom={12} 
            style={{ flex: 1, width: '100%', border: 'none' }}
          >
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; OpenStreetMap contributors' />
            <MapBoundsController bounds={mapBounds} />
            <MapResizeController chatOpen={isChatOpen} />
            <SocalFireOverlays
              imageType={imageType}
              imageTransforms={imageTransforms}
              availableImageSet={availableImageSet}
            />
            <LabelPolygonOverlays
              polygons={labelPolygons}
              imageType={imageType}
            />
            <HouseConditionOverlays
              houses={houseObservations}
              imageTransformsById={imageTransformsById}
              imageType={imageType}
            />
            <GeoJSON data={polygons} style={getPolygonStyle} onEachFeature={onEachFeature} />
          </MapContainer>
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
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '12px',
                flexWrap: 'wrap',
                width: '100%'
              }}
            >
              {damageLegendItems.map((item) => (
                <div key={item.key} style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#ffffff', fontSize: '13px' }}>
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
        </div>
        {isChatOpen && (
          <div style={{ position: 'relative', flex: 0.5, minWidth: '280px', maxWidth: '420px', display: 'flex', flexDirection: 'column', border: '1px solid #ddd', borderRadius: '10px', margin: '10px' }}>
            <button
              type="button"
              onClick={() => setIsChatOpen(false)}
              style={{
                position: 'absolute',
                top: '8px',
                right: '8px',
                zIndex: 2,
                padding: '6px 12px',
                borderRadius: '8px'
              }}
            >
              Hide
            </button>

            <div style={{ flex: 1, overflowY: 'auto', padding: '38px 10px 10px' }}>
              {messages.map((msg, index) => (
                <div key={index} style={{ marginBottom: '10px', textAlign: msg.sender === 'user' ? 'right' : 'left' }}>
                  <span style={{ background: '#f1f1f1', color: 'black', padding: '8px', borderRadius: '10px' }}>{msg.text}</span>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', padding: '10px' }}>
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                style={{ flex: 1, padding: '8px' }}
                placeholder="Type a message..."
                disabled={isLoading}
              />
              <button onClick={sendMessage} disabled={isLoading} style={{ padding: '8px 16px' }}>
                {isLoading ? 'Sending...' : 'Send'}
              </button>
            </div>
          </div>
        )}
        {!isChatOpen && (
          <button
            type="button"
            onClick={() => setIsChatOpen(true)}
            style={{
              position: 'absolute',
              right: '10px',
              top: '10px',
              transform: 'rotate(180deg)',
              padding: '12px 8px',
              borderTopLeftRadius: '10px',
              borderBottomLeftRadius: '10px',
              writingMode: 'vertical-rl',
              textOrientation: 'mixed',
              letterSpacing: '0.08em',
              zIndex: 1200
            }}
          >
            Chat
          </button>
        )}
      </div>
    </div>
  );
}

export default App
