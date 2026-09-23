const MAX_PULSE_CATEGORIES = 6;

export const toAmount = (value) => {
  const amount = Number(value);
  return Number.isFinite(amount) && amount > 0 ? amount : 0;
};

const allocateRoundedPercentages = (items, totalSpent) => {
  if (totalSpent <= 0) {
    return items.map((item) => ({ ...item, percentage: 0 }));
  }

  const percentages = items.map((item) => (item.amount / totalSpent) * 100);
  const rounded = percentages.map(Math.floor);
  let pointsLeft = Math.max(
    0,
    100 - rounded.reduce((sum, value) => sum + value, 0)
  );

  percentages
    .map((value, index) => ({ index, remainder: value - Math.floor(value) }))
    .sort((left, right) => right.remainder - left.remainder)
    .forEach(({ index }) => {
      if (pointsLeft > 0) {
        rounded[index] += 1;
        pointsLeft -= 1;
      }
    });

  return items.map((item, index) => ({
    ...item,
    percentage: rounded[index]
  }));
};

export const buildPulseCategories = (analysis) => {
  const sourceCategories = (analysis?.by_category || [])
    .map((item) => ({
      ...item,
      amount: toAmount(item.amount),
      sourceCategories: [item.category]
    }))
    .filter((item) => item.amount > 0)
    .sort((left, right) => right.amount - left.amount);
  const categoryTotal = sourceCategories.reduce(
    (sum, item) => sum + item.amount,
    0
  );
  const reportedTotal = toAmount(analysis?.total_spent);
  const totalSpent = reportedTotal || categoryTotal;
  const unclassifiedAmount = Math.max(0, totalSpent - categoryTotal);
  const needsAggregation = (
    sourceCategories.length > MAX_PULSE_CATEGORIES ||
    unclassifiedAmount > 0.005
  );

  if (!needsAggregation) {
    return allocateRoundedPercentages(sourceCategories, totalSpent);
  }

  const explicitlyOther = sourceCategories.filter(
    (item) => item.category?.trim().toLowerCase() === "other"
  );
  const individualCategories = sourceCategories.filter(
    (item) => item.category?.trim().toLowerCase() !== "other"
  );
  const visibleCount = Math.min(
    MAX_PULSE_CATEGORIES - 1,
    individualCategories.length
  );
  const visibleCategories = individualCategories.slice(0, visibleCount);
  const remainingCategories = [
    ...individualCategories.slice(visibleCount),
    ...explicitlyOther
  ];
  const otherAmount = remainingCategories.reduce(
    (sum, item) => sum + item.amount,
    unclassifiedAmount
  );

  if (otherAmount > 0) {
    visibleCategories.push({
      category: "Other",
      amount: otherAmount,
      sourceCategories: [...new Set(
        remainingCategories.map((item) => item.category)
      )],
      isAggregate: true
    });
  }

  return allocateRoundedPercentages(visibleCategories, totalSpent);
};
