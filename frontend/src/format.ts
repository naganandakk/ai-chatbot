// Replies often cost fractions of a cent, so keep enough digits to show them
export const formatCost = (usd: number) => new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 6,
}).format(usd);

// Two significant digits for places with little room, e.g. $0.0123 becomes $0.012
export const formatCostShort = (usd: number) => new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumSignificantDigits: 2,
}).format(usd);

// Share of the input tokens that were read from the prompt cache, e.g. "83%". Null when the
// reply had no input to compare against
export const formatCacheHit = (cacheReadTokens: number, inputTokens: number) => {
  if (inputTokens <= 0) {
    return null;
  }

  return new Intl.NumberFormat('en-US', {
    style: 'percent',
    maximumFractionDigits: 0,
  }).format(cacheReadTokens / inputTokens);
};
