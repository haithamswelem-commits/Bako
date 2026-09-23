export function formatSubcategoryName(name) {
  if (typeof name !== "string") {
    return name;
  }

  return name.trim().toLowerCase() === "haasan" ? "Hassan" : name;
}
