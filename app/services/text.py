import re


def clean_description(raw: str) -> str:
    if raw is None or (isinstance(raw, float) and str(raw) == "nan"):
        return ""
    s = str(raw).strip()
    s = re.sub(r"\s+", " ", s)
    return s.upper()


def normalize_type(value) -> str:
    s = str(value).strip().lower()
    if s not in ("credit", "debit"):
        raise ValueError(f"Invalid type: {value!r}; expected credit or debit")
    return s
