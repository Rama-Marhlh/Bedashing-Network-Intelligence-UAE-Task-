export const formatNumber = (
  value: number | null | undefined,
  maximumFractionDigits = 0,
): string =>
  value === null || value === undefined
    ? "Not available"
    : new Intl.NumberFormat("en-US", { maximumFractionDigits }).format(value);

export const formatPercent = (value: number | null | undefined): string =>
  value === null || value === undefined ? "Not available" : `${formatNumber(value, 1)}%`;

export const formatRating = (value: number | null | undefined): string =>
  value === null || value === undefined ? "Not available" : `${value.toFixed(2)} / 5`;
