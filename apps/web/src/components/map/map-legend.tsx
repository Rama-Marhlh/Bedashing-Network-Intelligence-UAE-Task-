export function MapLegend() {
  return (
    <div className="map-legend" aria-label="Map legend">
      <strong>Legend</strong>
      <span>
        <i className="legend-symbol branch-symbol" /> Branch decision: shape + color
      </span>
      <span>
        <i className="legend-symbol direct-symbol" /> Direct competitor
      </span>
      <span>
        <i className="legend-symbol adjacent-symbol" /> Adjacent competitor
      </span>
      <span>
        <i className="legend-symbol shortlist-symbol" /> Reviewed search area
      </span>
      <span>
        <i className="legend-symbol catchment-symbol" /> Modelled drive-time catchment
      </span>
    </div>
  );
}
