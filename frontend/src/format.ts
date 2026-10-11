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
