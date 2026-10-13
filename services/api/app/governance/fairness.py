"""Fair-lending checks: the same lead under synthetic names that span gender and ethnicity, and under three countries,
must be scored and read the same. None of these names belongs to a real person."""

NAME_VARIANTS: list[str] = ["Emily Walsh", "DeShawn Washington", "Mei Lin Chen", "José Hernández", "Aisha Bello",
                            "Priyanka Iyer"]
COUNTRIES: list[str] = ["US", "GB", "SG"]


def variants(fields: dict, names: list[str], countries: list[str]) -> list[dict]:
    """Copies of a lead's fields with only the full name and the country changed: every name in every country."""
    return [{**fields, "full_name": name, "country": country} for name in names for country in countries]
