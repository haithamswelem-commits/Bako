"""Find and archive legacy category names that violate current validation."""

from __future__ import annotations


def contains_letter(value: str) -> bool:
    return any(character.isalpha() for character in value)


def find_invalid_categories(client) -> tuple[list[dict], list[dict]]:
    invalid_categories = []
    invalid_subcategories = []

    for category in client.request("GET", "/categories"):
        if not contains_letter(category["name"]):
            invalid_categories.append(category)
            continue

        subcategories = client.request(
            "GET",
            "/subcategories",
            query={"category_id": category["id"]},
        )
        invalid_subcategories.extend(
            {
                **subcategory,
                "category_id": category["id"],
                "category_name": category["name"],
            }
            for subcategory in subcategories
            if not contains_letter(subcategory["name"])
        )

    return invalid_categories, invalid_subcategories


def cleanup_invalid_categories(client, apply: bool = False) -> tuple[int, int]:
    invalid_categories, invalid_subcategories = find_invalid_categories(client)
    action = "Archiving" if apply else "Would archive"

    for category in invalid_categories:
        print(f"{action} spending group {category['id']}: {category['name']!r}")
        if apply:
            client.request("DELETE", f"/categories/{category['id']}")

    for subcategory in invalid_subcategories:
        print(
            f"{action} expense type {subcategory['id']}: "
            f"{subcategory['category_name']!r} / {subcategory['name']!r}"
        )
        if apply:
            client.request("DELETE", f"/subcategories/{subcategory['id']}")

    if not invalid_categories and not invalid_subcategories:
        print("No invalid numeric-only spending groups or expense types found.")
    elif not apply:
        print("Preview only. Run cleanup-categories to archive these records.")

    return len(invalid_categories), len(invalid_subcategories)
