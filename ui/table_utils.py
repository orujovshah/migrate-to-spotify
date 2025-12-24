def normalize_table_rows(tracks_dataframe):
    if tracks_dataframe is None:
        return []
    if hasattr(tracks_dataframe, "values"):
        return tracks_dataframe.values.tolist()
    return tracks_dataframe


def sanitize_selection_column(rows):
    cleaned = []
    changed = False
    for row in rows or []:
        if isinstance(row, (list, tuple)):
            new_row = list(row)
        else:
            new_row = [row]
        if new_row:
            value = new_row[0]
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in ("true", "false"):
                    new_row[0] = lowered == "true"
                    changed = True
            elif isinstance(value, int) and not isinstance(value, bool) and value in (0, 1):
                new_row[0] = bool(value)
                changed = True
        cleaned.append(new_row)
    return cleaned, changed
