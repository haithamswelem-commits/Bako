import { useMemo, useState } from "react";

import { formatCurrency } from "../utils/formatCurrency";
import { formatSubcategoryName } from "../utils/displayNames";
import { buildPulseCategories, toAmount } from "../utils/spendingPulse";

function SpendingAnalysis({ analysis, cycleName = "", amountsHidden = false }) {
  const [selectedCategory, setSelectedCategory] = useState(null);
  const categories = useMemo(() => buildPulseCategories(analysis), [analysis]);
  const totalSpent = toAmount(analysis?.total_spent) || categories.reduce(
    (sum, item) => sum + item.amount,
    0
  );
  const activeCategoryData = categories.find(
    (item) => item.category === selectedCategory
  );
  const activeCategoryNames = activeCategoryData?.sourceCategories || [];
  const activeSubcategories = (analysis?.by_subcategory || [])
    .filter((item) => activeCategoryNames.includes(item.category))
    .sort((left, right) => toAmount(right.amount) - toAmount(left.amount))
    .slice(0, 4);
  const lineHeight = Math.max(160, categories.length * 100);
  const pulsePoints = categories.map((_, index) => {
    const x = index % 2 === 0 ? 43 : 60;
    const y = ((index + 0.5) / categories.length) * 100;
    return `${x},${y}`;
  }).join(" ");

  if (!analysis) {
    return <p className="empty-text">No spending data yet.</p>;
  }

  return (
    <div className="spending-tile-analysis spending-pulse-analysis">
      {!activeCategoryData && (
        <>
          <span className="spending-pulse-cycle" title={cycleName || "Current cycle"}>
            {cycleName || "Current cycle"}
          </span>
          <section
            className="spending-pulse-total"
            aria-label={amountsHidden ? "Total spent, amount hidden" : `Total spent, ${formatCurrency(totalSpent)}`}
          >
            <span>Total Spent</span>
            <strong>{formatCurrency(totalSpent)}</strong>
          </section>
        </>
      )}

      {!activeCategoryData ? (
        categories.length === 0 ? (
          <p className="spending-pulse-empty">No spending data yet.</p>
        ) : (
          <div
            className="spending-pulse-line"
            style={{ height: `${lineHeight}px` }}
          >
            <svg
              className="spending-pulse-connectors"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              aria-hidden="true"
              focusable="false"
            >
              <polyline points={pulsePoints} />
            </svg>

            {categories.map((item, index) => {
              const isLeft = index % 2 === 0;
              const y = ((index + 0.5) / categories.length) * 100;
              const accessibleLabel = amountsHidden
                ? `${item.category}, ${item.percentage} percent, amount hidden.`
                : `${item.category}, ${item.percentage} percent, ${formatCurrency(item.amount)}.`;

              return (
                <button
                  className={`spending-pulse-category ${isLeft ? "is-left" : "is-right"}`}
                  key={`${item.category}-${index}`}
                  onClick={() => setSelectedCategory(item.category)}
                  type="button"
                  style={{ top: `${y}%` }}
                  aria-label={accessibleLabel}
                >
                  <span className="spending-pulse-node" aria-hidden="true" />
                  <span className="spending-pulse-copy">
                    <b>{item.percentage}%</b>
                    <strong>{item.category}</strong>
                    <span>{formatCurrency(item.amount)}</span>
                  </span>
                </button>
              );
            })}
          </div>
        )
      ) : (
        <section className="spending-category-detail">
          <div className="analysis-detail-cycle-summary">
            <div>
              <span>Current cycle</span>
              <strong title={cycleName || "Current cycle"}>
                {cycleName || "Current cycle"}
              </strong>
            </div>
            <div>
              <span>Total spent</span>
              <strong>{formatCurrency(totalSpent)}</strong>
            </div>
          </div>

          <div className="analysis-subcategory-heading">
            <div>
              <span>{activeCategoryData.category}</span>
              <small>Subcategory spend</small>
            </div>
            <strong>{formatCurrency(activeCategoryData.amount)}</strong>
          </div>

          <div className="analysis-subcategory-list">
            {activeSubcategories.length === 0 ? (
              <p className="analysis-subcategory-empty">
                No subcategory breakdown yet.
              </p>
            ) : (
              activeSubcategories.map((item) => (
                <div
                  className="analysis-subcategory-row"
                  key={`${item.category}-${item.subcategory}`}
                >
                  <div className="analysis-subcategory-copy">
                    <span>{formatSubcategoryName(item.subcategory)}</span>
                    <strong>{formatCurrency(item.amount)}</strong>
                  </div>
                  <em>{Math.round(item.percentage_of_category || 0)}%</em>
                </div>
              ))
            )}
          </div>

          <button
            className="analysis-detail-close pulse-black-action"
            onClick={() => setSelectedCategory(null)}
            type="button"
          >
            <span className="pulse-black-action-arrow" aria-hidden="true">←</span>
            <span>Back to categories</span>
          </button>
        </section>
      )}
    </div>
  );
}

export default SpendingAnalysis;
