export const formatCurrency = (value) => {
  if (value === null || value === undefined) {
    return "EGP 0";
  }

  return new Intl.NumberFormat("en-EG", {
    style: "currency",
    currency: "EGP",
    minimumFractionDigits: 2
  }).format(value);
};